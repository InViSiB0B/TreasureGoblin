"""
TreasureGoblin Import/Export Utilities

Handles database import and export operations for TreasureGoblin.
"""

from datetime import datetime
import json
import shutil
import sqlite3
import tempfile
import zipfile
from pathlib import Path

from PyQt5.QtWidgets import QFileDialog, QMessageBox


class TreasureGoblinImportExport:
    """Helper class for handling import/export operations in TreasureGoblin."""

    def __init__(self, treasure_goblin):
        """
        Initialize with a reference to the TreasureGoblin instance.

        Args:
            treasure_goblin: Reference to the TreasureGoblin instance
        """
        self.treasure_goblin = treasure_goblin

    def export_database(self):
        """
        Export the entire database to a zip archive.

        Returns:
            Tuple (success: bool, message: str) indicating operation result
        """
        try:
            # Ask user for export location
            export_file, _ = QFileDialog.getSaveFileName(
                None,
                "Export Financial Data",
                str(Path.home() / "TreasureGoblin_Export.zip"),
                "Zip Files (*.zip)"
            )

            if not export_file:
                return False, "Export cancelled"

            # Get database path
            db_path = self.treasure_goblin.db_path

            # Create a timestamp for the backup file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"treasuregoblin_backup_{timestamp}.zip"

            # Create a temporary directory for the export
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Copy database file
                db_dest = temp_path / "treasuregoblin.db"
                shutil.copy2(db_path, db_dest)

                # Create metadata file
                metadata = {
                    "export_date": datetime.now().isoformat(),
                    "app_version": "1.0",
                    "transaction_count": self._get_transaction_count()
                }

                with open(temp_path / "metadata.json", "w") as f:
                    json.dump(metadata, f, indent=2)

                # Create the zip file
                with zipfile.ZipFile(export_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    # Add database and metadata files
                    zipf.write(db_dest, "treasuregoblin.db")
                    zipf.write(temp_path / "metadata.json", "metadata.json")

            # Store the path for later reference
            self.last_export_path = export_file

            return True, f"Successfully exported to {export_file}"

        except Exception as e:
            return False, f"Export failed: {str(e)}"

    def _get_transaction_count(self):
        """
        Get count of transactions in the database.

        Returns:
            Dict containing transaction counts by type and total
        """
        try:
            conn = self.treasure_goblin.get_db_connection()
            cursor = conn.cursor()

            # Get total count
            cursor.execute("SELECT COUNT(*) FROM transactions")
            total = cursor.fetchone()[0]

            # Get income count
            cursor.execute("SELECT COUNT(*) FROM transactions WHERE type = 'income'")
            income = cursor.fetchone()[0]

            # Get expense count
            cursor.execute("SELECT COUNT(*) FROM transactions WHERE type = 'expense'")
            expense = cursor.fetchone()[0]

            conn.close()

            return {
                "total": total,
                "income": income,
                "expense": expense
            }
        except:
            return {"total": 0, "income": 0, "expense": 0}

    def import_database(self, merge=True):
        """
        Import a database from a previously exported zip archive.

        Args:
            merge: If True, merge imported transactions with existing ones.
                  If False, replace the existing database.

        Returns:
            Tuple (success: bool, message: str) indicating operation result
        """
        try:
            # Ask user for import file
            import_file, _ = QFileDialog.getOpenFileName(
                None,
                "Import Financial Data",
                str(Path.home()),
                "Zip Files (*.zip)"
            )

            if not import_file:
                return False, "Import cancelled"

            # Confirm import
            confirm_msg = QMessageBox()
            confirm_msg.setIcon(QMessageBox.Warning)
            confirm_msg.setWindowTitle("Confirm Import")

            if merge:
                confirm_msg.setText("Merge imported transactions with your current data?")
                confirm_msg.setInformativeText(
                    "This will add the imported transactions to your existing financial history.")
            else:
                confirm_msg.setText("Importing will replace your current financial data.")
                confirm_msg.setInformativeText("Are you sure you want to proceed? This cannot be undone.")

            confirm_msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            confirm_msg.setDefaultButton(QMessageBox.No)

            if confirm_msg.exec_() != QMessageBox.Yes:
                return False, "Import cancelled"

            # Get database path
            db_path = self.treasure_goblin.db_path

            # Create a temporary directory for the import
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Close all existing database connections first
                try:
                    conn = self.treasure_goblin.get_db_connection()
                    conn.close()
                except:
                    pass

                # Extract the zip file
                with zipfile.ZipFile(import_file, 'r') as zipf:
                    zipf.extractall(temp_path)

                # Verify this is a valid export
                if not (temp_path / "treasuregoblin.db").exists():
                    return False, "Invalid export file: Missing database"

                if not (temp_path / "metadata.json").exists():
                    return False, "Invalid export file: Missing metadata"

                # Read metadata
                with open(temp_path / "metadata.json", "r") as f:
                    metadata = json.load(f)

                import_db_path = temp_path / "treasuregoblin.db"

                if merge:
                    # Merge databases
                    imported_count, skipped_count = self._merge_databases(db_path, import_db_path)
                    return True, f"Successfully imported and merged {imported_count} transactions. {skipped_count} duplicate transactions were skipped."
                else:

                    # Create a backup of the current database
                    backup_path = str(db_path) + ".backup"
                    shutil.copy2(db_path, backup_path)

                    # Make sure SQLite isn't using the file
                    import time

                    # Close connections and wait a moment for OS to release file locks
                    time.sleep(0.5)

                    # Copy the file
                    try:
                        shutil.copy2(import_db_path, db_path)
                    except PermissionError:
                        # If we still have permission issues, try an alternative approach
                        with open(import_db_path, 'rb') as src, open(db_path, 'wb') as dst:
                            dst.write(src.read())

                    transaction_count = metadata.get("transaction_count", {})
                    total_count = transaction_count.get("total", "unknown")

                    return True, f"Successfully imported {total_count} transactions"

        except Exception as e:
            # Restore from backup if available and not merging
            if not merge and 'backup_path' in locals():
                try:
                    shutil.copy2(backup_path, db_path)
                except Exception as backup_error:
                    return False, f"Import failed: {str(e)}\nAlso failed to restore backup: {str(backup_error)}"

            return False, f"Import failed: {str(e)}"

    def _merge_databases(self, current_db_path, import_db_path):
        """
        Merge two SQLite databases, importing transactions from import_db to current_db.

        Args:
            current_db_path: Path to the current database
            import_db_path: Path to the database being imported

        Returns:
            Tuple of (imported_count, skipped_count)
        """
        # Connect to current database
        current_conn = None
        import_conn = None

        try:
            # Track how many transactions we import and skip
            imported_count = 0
            skipped_count = 0

            # Open connections with retry logic
            for attempt in range(3):
                try:
                    # Connect to current database
                    current_conn = sqlite3.connect(current_db_path)
                    current_cursor = current_conn.cursor()

                    # Connect to imported database
                    import_conn = sqlite3.connect(f"file:{import_db_path}?mode=ro", uri=True)  # Read-only mode
                    import_conn.row_factory = sqlite3.Row
                    import_cursor = import_conn.cursor()
                    break
                except sqlite3.OperationalError as e:
                    if attempt == 2:  # Last attempt failed
                        raise e
                    import time
                    time.sleep(1)  # Wait before retrying

            # Enable foreign keys
            current_cursor.execute("PRAGMA foreign_keys = ON")

            # Begin transaction
            current_conn.execute("BEGIN TRANSACTION")

            # Get all categories from the import database
            import_cursor.execute("SELECT id, name, type FROM categories")
            categories = import_cursor.fetchall()

            # Get existing categories to avoid duplicates
            current_cursor.execute("SELECT id, name, type FROM categories")
            existing_categories = {(row[1], row[2]): row[0] for row in current_cursor.fetchall()}

            # Import categories
            category_mapping = {}  # Maps imported category IDs to existing/new category IDs

            for category in categories:
                cat_id, cat_name, cat_type = category

                # If category name already exists, map to existing ID
                if (cat_name, cat_type) in existing_categories:
                    category_mapping[cat_id] = existing_categories[(cat_name, cat_type)]
                else:
                    # Otherwise, insert the category
                    current_cursor.execute(
                        "INSERT INTO categories (name, type) VALUES (?, ?)",
                        (cat_name, cat_type)
                    )
                    new_id = current_cursor.lastrowid
                    category_mapping[cat_id] = new_id

            # Get existing transactions to check for duplicates
            current_cursor.execute("""
                SELECT t.date, t.amount, t.type, c.name
                FROM transactions t
                JOIN categories c ON t.category_id = c.id
            """)
            existing_transactions = set()
            for row in current_cursor.fetchall():
                date, amount, type_val, category = row
                # Ensure consistent formatting for comparison
                date_str = date.strip() if isinstance(date, str) else date
                amount_float = float(amount)
                existing_transactions.add((date_str, amount_float, type_val, category))

            # Import transactions from source database
            import_cursor.execute("""
                SELECT t.id, t.type, t.amount, t.date, t.category_id, t.tag, c.name as category_name
                FROM transactions t
                JOIN categories c ON t.category_id = c.id
            """)

            transactions = import_cursor.fetchall()

            # Process each transaction
            for transaction in transactions:
                transaction_dict = dict(transaction)

                # Create tuple for duplicate checking
                transaction_tuple = (
                    transaction_dict['date'].strip() if isinstance(transaction_dict['date'],
                                                                    str) else transaction_dict['date'],
                    float(transaction_dict['amount']),
                    transaction_dict['type'],
                    transaction_dict['category_name']
                )

                # Skip if this transaction already exists
                if transaction_tuple in existing_transactions:
                    skipped_count += 1
                    continue

                # Update category ID mapping
                mapped_category_id = category_mapping.get(transaction_dict['category_id'])
                if mapped_category_id is None:
                    # If no mapping exists (unusual case), use a default category
                    default_query = "SELECT id FROM categories WHERE type = ? LIMIT 1"
                    current_cursor.execute(default_query, (transaction_dict['type'],))
                    result = current_cursor.fetchone()
                    if result:
                        mapped_category_id = result[0]
                    else:
                        # Create a default category if none exists
                        default_name = "Other Income" if transaction_dict['type'] == 'income' else "Other Expense"
                        current_cursor.execute(
                            "INSERT INTO categories (name, type) VALUES (?, ?)",
                            (default_name, transaction_dict['type'])
                        )
                        mapped_category_id = current_cursor.lastrowid

                # Insert transaction with a new ID (don't preserve old IDs)
                current_cursor.execute("""
                    INSERT INTO transactions
                    (type, amount, date, category_id, tag)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    transaction_dict['type'],
                    transaction_dict['amount'],
                    transaction_dict['date'],
                    mapped_category_id,
                    transaction_dict['tag']
                ))

                # Add to existing set to avoid duplicates in the import file
                existing_transactions.add(transaction_tuple)
                imported_count += 1

            # Commit all changes
            current_conn.commit()

            return imported_count, skipped_count

        except Exception as e:
            # Roll back on error
            if current_conn:
                current_conn.rollback()
            raise e

        finally:
            # Close connections
            if current_conn:
                current_conn.close()
            if import_conn:
                import_conn.close()
