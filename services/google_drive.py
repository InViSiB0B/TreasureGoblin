"""
TreasureGoblin Google Drive Sync Service

Handles Google Drive synchronization and backup functionality.
"""

from datetime import datetime
import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path

from PyQt5.QtCore import QObject, pyqtSignal, QTimer
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
                             QLabel, QPushButton, QCheckBox, QComboBox,
                             QFormLayout, QProgressBar, QMessageBox, QApplication)
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


class GoogleDriveSync(QObject):
    """Class for handling Google Drive synchronization of TreasureGoblin data."""

    # Define signals, for UI updates
    sync_started = pyqtSignal()
    sync_completed = pyqtSignal(bool, str)  # Success flag and message
    sync_progress = pyqtSignal(int)  # Progress percentage

    # Scopes required for Google Drive API
    SCOPES = ['https://www.googleapis.com/auth/drive.file']

    def __init__(self, treasure_goblin):
        super().__init__()
        self.treasure_goblin = treasure_goblin

        self.user_config_dir = Path.home() / ".treasuregoblin"
        self.user_config_dir.mkdir(exist_ok=True)

        self.app_dir = treasure_goblin.app_dir
        self.config_file = self.user_config_dir / "drive_sync.json"

        # Default configuration
        self.config = {
            'sync_enabled': False,
            'sync_frequency': 'manual',  # 'manual, 'app_close', 'daily', 'weekly', 'monthly'
            'last_sync': None,
            'sync_folder_id': None,  # Google Drive folder ID where backups are stored
            'sync_file_id': None,  # Latest file ID on Google Drive
            'token': None  # OAuth token info
        }

        # Load existing configuration if available
        self.load_config()

    def load_config(self):
        """Load Google Drive sync configuration from file."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    saved_config = json.load(f)

                    # Update config with saved values
                    self.config.update(saved_config)
            except Exception as e:
                print(f"Error loading Drive sync config: {e}")

    def save_config(self):
        """Save Google Drive sync configuration to file."""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"Error saving Drive sync config: {e}")

    def get_credentials(self):
        """Get and refresh Google Drive API credentials."""
        creds = None

        # Load token from config if available
        if self.config['token']:
            creds = Credentials.from_authorized_user_info(self.config['token'], self.SCOPES)

        # If credentials are invalid or expired, refresh or authenticate
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    print(f"Error refreshing credentials: {e}")
                    return None
            else:
                # Look for client secret file with the full filename
                try:
                    # Define the path to the client secret file
                    script_dir = os.path.dirname(os.path.abspath(__file__))
                    client_config_file = os.path.join(
                        script_dir,
                        "client_secret_201372032136-ev7nhopm297avo3lotgufftvlb6kgao2.apps.googleusercontent.com.json"
                    )

                    # Check if the file exists
                    if not os.path.exists(client_config_file):
                        # Try in app_dir as fallback
                        client_config_file = self.app_dir / "client_secret_201372032136-ev7nhopm297avo3lotgufftvlb6kgao2.apps.googleusercontent.com.json"

                        # If still not found, try with a simpler name
                        if not os.path.exists(client_config_file):
                            client_config_file = self.app_dir / "client_secret.json"

                            # If even simpler name not found, use embedded credentials
                            if not os.path.exists(client_config_file):
                                raise FileNotFoundError("Client secret file not found")

                    # Use the file for authentication
                    flow = InstalledAppFlow.from_client_secrets_file(
                        client_config_file, self.SCOPES)
                    creds = flow.run_local_server(port=0)

                except FileNotFoundError:
                    # Fallback to embedded credentials
                    print("Using embedded credentials as fallback...")
                    client_config = {
                        "installed": {
                            "client_id": self.CLIENT_ID,
                            "client_secret": self.CLIENT_SECRET,
                            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                            "token_uri": "https://oauth2.googleapis.com/token",
                            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"]
                        }
                    }

                    flow = InstalledAppFlow.from_client_config(
                        client_config, self.SCOPES)
                    creds = flow.run_local_server(port=0)

            # Save the updated token
            self.config['token'] = json.loads(creds.to_json())
            self.save_config()

        return creds

    def get_drive_service(self):
        """Create and return a Google Drive API service instance."""
        creds = self.get_credentials()
        if not creds:
            return None

        return build('drive', 'v3', credentials=creds)

    def ensure_backup_folder(self, service):
        """Ensure the TreasureGoblin backup folder exists in Google Drive."""
        folder_id = self.config['sync_folder_id']

        # Check if there is already a folder ID and it exists
        if folder_id:
            try:
                folder = service.files().get(fileId=folder_id).execute()
                return folder_id
            except Exception:
                # Folder doesn't exist, need to create a new one
                folder_id = None

        # Create a new folder
        folder_metadata = {
            'name': 'TreasureGoblin Backups',
            'mimeType': 'application/vnd.google-apps.folder'
        }

        folder = service.files().create(body=folder_metadata, fields='id').execute()
        folder_id = folder.get('id')

        # Save the folder ID
        self.config['sync_folder_id'] = folder_id
        self.save_config()

        return folder_id

    def create_backup_file(self):
        """Create a backup zip file of the database directly without user interaction."""
        try:
            # Get database path
            db_path = self.treasure_goblin.db_path

            # Create a timestamp for the backup file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"treasuregoblin_backup_{timestamp}.zip"

            # Create the backup in app's temp directory
            temp_dir = self.app_dir / "temp"
            temp_dir.mkdir(exist_ok=True)

            backup_file_path = temp_dir / backup_filename

            # Create a temporary directory for assembling the backup
            with tempfile.TemporaryDirectory() as temp_assembly_dir:
                temp_path = Path(temp_assembly_dir)

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
                with zipfile.ZipFile(backup_file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    # Add database and metadata files
                    zipf.write(db_dest, "treasuregoblin.db")
                    zipf.write(temp_path / "metadata.json", "metadata.json")

            return str(backup_file_path)

        except Exception as e:
            print(f"Error creating direct backup file: {e}")
            return None

    def upload_backup(self, backup_file_path):
        """Upload the backup file to Google Drive."""
        try:
            # Check if backup_file is None or empty
            if not backup_file_path:
                return False, "No valid backup file was created. Check previous errors."

            service = self.get_drive_service()
            if not service:
                return False, "Failed to connect to Google Drive."

            # Ensure backup folder exists
            folder_id = self.ensure_backup_folder(service)

            # Prepare file metadata
            file_metadata = {
                'name': os.path.basename(backup_file_path),
                'parents': [folder_id]
            }

            # Get file size for progress tracking
            # file_size = os.path.getsize(backup_file_path)

            # Start with 0% progress
            self.sync_progress.emit(0)

            # Prepare the media upload
            media = MediaFileUpload(
                backup_file_path,
                mimetype='application/zip',
                resumable=True,
                chunksize=256 * 1024
            )

            # Upload file with progress tracking
            request = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            )

            response = None
            last_progress = 0

            # Update progress as chunks are uploaded
            while response is None:
                try:
                    status, response = request.next_chunk()
                    if status:
                        # Calculate progress percentage
                        current_progress = int(status.progress() * 100)

                        # Only emit progress updates when the value changes
                        if current_progress != last_progress:
                            self.sync_progress.emit(current_progress)
                            last_progress = current_progress

                            # Process events to allow UI updates
                            QApplication.processEvents()

                    # Small delay to allow UI updates
                    import time
                    time.sleep(0.01)

                except Exception as chunk_error:
                    print(f"Error during chunk upload: {chunk_error}")
                    raise chunk_error

            # Save the file ID
            self.config['sync_file_id'] = response.get('id')
            self.config['last_sync'] = datetime.now().isoformat()
            self.save_config()

            # Ensure 100% progress is shown when done
            self.sync_progress.emit(100)
            QApplication.processEvents()

            return True, "Backup successfully uploaded to Google Drive"

        except Exception as e:
            print(f"Error uploading backup: {e}")
            return False, f"Error uploading backup: {str(e)}"

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

    def sync_now(self):
        """Perform an immediate sync to Google Drive."""
        try:
            self.sync_started.emit()

            # Create backup file
            backup_file_path = self.create_backup_file()

            if not backup_file_path:
                self.sync_completed.emit(False, "Failed to create backup file")
                return False, "Failed to create backup file"

            # Upload to Google Drive
            success, message = self.upload_backup(backup_file_path)

            # Clean up the temporary file after upload
            try:
                os.remove(backup_file_path)
            except:
                # Don't fail if cleanup fails
                pass

            # Emit completion signal
            self.sync_completed.emit(success, message)

            return success, message

        except Exception as e:
            error_message = f"Sync failed: {str(e)}"
            self.sync_completed.emit(False, error_message)
            return False, error_message

    def should_sync_on_close(self):
        """Check if backup should be synced on application close."""
        if not self.config['sync_enabled']:
            return False

        frequency = self.config['sync_frequency']

        if frequency == 'app_close':
            return True

        if frequency == 'daily':
            # Check if last sync was more than a day ago
            if not self.config['last_sync']:
                return True

            last_sync = datetime.fromisoformat(self.config['last_sync'])
            now = datetime.now()
            return (now - last_sync).days >= 1

        if frequency == 'weekly':
            # Check if last sync was more than a week ago
            if not self.config['last_sync']:
                return True

            last_sync = datetime.fromisoformat(self.config['last_sync'])
            now = datetime.now()
            return (now - last_sync).days >= 7

        if frequency == 'monthly':
            # Check if last sync was more than a month ago
            if not self.config['last_sync']:
                return True

            last_sync = datetime.fromisoformat(self.config['last_sync'])
            now = datetime.now()
            return (now - last_sync).days >= 30

        return False

    def sync_on_close(self):
        """Perform sync on application close if needed."""
        if self.should_sync_on_close():
            return self.sync_now()
        return False, "Sync not needed based on current settings."


class GoogleDriveSyncDialog(QDialog):
    """Dialog for configuring Google Drive synchronization settings."""

    def __init__(self, parent, drive_sync):
        super().__init__(parent)
        self.drive_sync = drive_sync
        self.init_ui()

    def init_ui(self):
        """Initialize the dialog UI."""
        self.setWindowTitle("Google Drive Sync Settings")
        self.setMinimumWidth(500)

        layout = QVBoxLayout(self)

        # Google Drive status section
        status_group = QGroupBox("Google Drive Status")
        status_group.setStyleSheet("font-size: 16px; font-weight: bold;")
        status_layout = QVBoxLayout(status_group)

        if self.drive_sync.config.get('token'):
            status_label = QLabel("Connected to Google Drive")
            status_label.setStyleSheet("color: green; font-weight: bold; font-size: 14px;")
        else:
            status_label = QLabel("Not connected to Google Drive")
            status_label.setStyleSheet("color: gray; font-size: 14px; font-weight: bold;")

        status_layout.addWidget(status_label)

        # Google account info if available
        if self.drive_sync.config.get('token'):
            try:
                # Try to extract email from token if available
                token_info = self.drive_sync.config.get('token', {})
                if isinstance(token_info, dict) and 'email' in token_info:
                    email = token_info['email']
                    account_label = QLabel(f"Connected Account: {email}")
                    account_label.setStyleSheet("font-size: 13px;")
                    status_layout.addWidget(account_label)
            except:
                pass

        # Authentication button
        auth_button_text = "Re-Connect" if self.drive_sync.config.get('token') else "Connect to Google Drive"
        self.auth_button = QPushButton(auth_button_text)
        self.auth_button.setStyleSheet("""
            QPushButton {
                background-color: #4285F4;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 10px 15px;
                border-radius: 6px;
                min-height: 35px;
            }
            QPushButton:hover {
                background-color: #3367D6;
            }
        """)
        self.auth_button.clicked.connect(self.authenticate)
        status_layout.addWidget(self.auth_button)

        # Add info about Google Drive access
        info_label = QLabel(
            "Connecting to Google Drive allows TreasureGoblin to automatically back up "
            "your financial data. The app will only have access to the files it creates "
            "in a folder named 'TreasureGoblin Backups'."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: gray; font-size: 12pt;")
        status_layout.addWidget(self.auth_button)

        layout.addWidget(status_group)

        # Enable sync checkbox
        self.enable_sync_checkbox = QCheckBox("Enable automatic Google Drive synchronization")
        self.enable_sync_checkbox.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.enable_sync_checkbox.setChecked(self.drive_sync.config.get('sync_enabled', False))
        self.enable_sync_checkbox.setEnabled(self.drive_sync.config.get('token') is not None)
        layout.addWidget(self.enable_sync_checkbox)

        # Sync frequency options
        sync_group = QGroupBox("Sync Frequency")
        sync_group.setStyleSheet("font-size: 16px; font-weight: bold;")
        sync_layout = QFormLayout(sync_group)

        self.frequency_combo = QComboBox()
        self.frequency_combo.addItem("Manual Only", "manual")
        self.frequency_combo.addItem("Every Time App Closes", "app_close")
        self.frequency_combo.addItem("Once Daily", "daily")
        self.frequency_combo.addItem("Once Weekly", "weekly")
        self.frequency_combo.addItem("Once Monthly", "monthly")
        self.frequency_combo.setStyleSheet("""
            QComboBox {
                font-size: 13px;
                font-weight: bold;
                padding: 8px 12px;
                min-height: 25px;
                border: 2px solid #ccc;
                border-radius: 4px;
            }
            QComboBox:focus {
                border: 2px solid #4285F4;
            }
        """)
        self.frequency_combo.setEnabled(self.drive_sync.config.get('token') is not None)

        # Set current value
        current_frequency = self.drive_sync.config.get('sync_frequency', 'manual')
        index = self.frequency_combo.findData(current_frequency)
        if index >= 0:
            self.frequency_combo.setCurrentIndex(index)

        frequency_label = QLabel("Backup Frequency:")
        frequency_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        sync_layout.addRow(frequency_label, self.frequency_combo)

        # Last sync information
        last_sync = self.drive_sync.config.get('last_sync')
        last_sync_text = "Never" if not last_sync else datetime.fromisoformat(last_sync).strftime("%m/%d/%Y %I:%M %p")
        self.last_sync_label = QLabel(f"Last Sync: {last_sync_text}")
        self.last_sync_label.setStyleSheet("font-size: 13px; color: #666;")
        sync_layout.addRow("", self.last_sync_label)

        layout.addWidget(sync_group)

        # Buttons
        button_layout = QHBoxLayout()

        self.sync_now_button = QPushButton("Sync Now")
        self.sync_now_button.setStyleSheet("""
            QPushButton {
                background-color: #4285F4;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 10px 15px;
                border-radius: 6px;
                min-height: 35px;
            }
            QPushButton:hover {
                background-color: #3367D6;
            }
            QPushButton:disabled {
                background-color: #ccc;
            }
        """)
        self.sync_now_button.clicked.connect(self.sync_now)
        self.sync_now_button.setEnabled(self.drive_sync.config.get('token') is not None)

        self.save_button = QPushButton("Save Settings")
        self.save_button.setStyleSheet("""
            QPushButton {
                background-color: #34A853;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 10px 15px;
                border-radius: 6px;
                min-height: 35px;
            }
            QPushButton:hover {
                background-color: #2E8B47;
            }
        """)
        self.save_button.clicked.connect(self.save_settings)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setStyleSheet("""
        QPushButton {
            background-color: #EA4335;
            color: white;
            font-size: 14px;
            font-weight: bold;
            padding: 10px 15px;
            border-radius: 6px;
            min-height: 35px;
        }
        QPushButton:hover {
            background-color: #D33B2C;
        }
    """)
        self.cancel_button.clicked.connect(self.reject)

        button_layout.addWidget(self.sync_now_button)
        button_layout.addStretch()
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

        # Progress bar (hidden initially)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                font-size: 12px;
                font-weight: bold;
                text-align: center;
                border: 2px solid #ccc;
                border-radius: 4px;
                background-color: #f0f0f0;
            }
            QProgressBar::chunk {
                background-color: #4285F4;
                border-radius: 2px;
            }
        """)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Connect signals
        self.drive_sync.sync_started.connect(self.on_sync_started)
        self.drive_sync.sync_completed.connect(self.on_sync_completed)
        self.drive_sync.sync_progress.connect(self.on_sync_progress)

    def authenticate(self):
        """Handle Google Drive authentication."""
        try:
            # Clear existing token to force new authentication
            self.drive_sync.config['token'] = None
            self.drive_sync.save_config()

            # Get new credentials (will launch browser auth)
            creds = self.drive_sync.get_credentials()

            if creds:
                # Update the UI
                self.setWindowTitle("Google Drive Sync Settings - Connecting...")
                QApplication.processEvents()  # Update the UI

                # Test the credentials with API call
                service = self.drive_sync.get_drive_service()
                if service:
                    about = service.about().get(fields="user").execute()
                    if "user" in about and "emailAddress" in about["user"]:
                        email = about["user"]["emailAddress"]
                        self.drive_sync.config['user_email'] = email
                        self.drive_sync.save_config()

                # Refresh the dialog
                self.close()
                new_dialog = GoogleDriveSyncDialog(self.parent(), self.drive_sync)
                new_dialog.exec_()
            else:
                QMessageBox.warning(self, "Authentication Failed", "Failed to connect to Google Drive.")

        except Exception as e:
            QMessageBox.critical(self, "Authentication Error", f"Error during authentication: {str(e)}")

    def sync_now(self):
        """Handle manual sync."""
        # Disable buttons during sync
        self.sync_now_button.setEnabled(False)
        self.save_button.setEnabled(False)
        self.cancel_button.setEnabled(False)

        # Show progress bar
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setVisible(True)

        # Create local progress handler
        def handle_progress(value):
            self.progress_bar.setValue(value)
            QApplication.processEvents()

        # Connect the progress signal
        self.drive_sync.sync_progress.connect(handle_progress)

        # Run sync directly (since we handle threading with processEvents)
        try:
            success, message = self.drive_sync.sync_now()
        finally:
            # Always disconnect the signal
            self.drive_sync.sync_progress.disconnect(handle_progress)

    def on_sync_started(self):
        """Handle sync started signal."""
        # Already being handled from sync_now
        pass

    def on_sync_progress(self, progress):
        """Handle sync progress signal."""
        self.progress_bar.setValue(progress)

        # Force the ui to update immediately
        QApplication.processEvents()

    def on_sync_completed(self, success, message):
        """Handle sync completed signal."""
        # Re-enable buttons
        self.sync_now_button.setEnabled(True)
        self.save_button.setEnabled(True)
        self.cancel_button.setEnabled(True)

        # Hide the progress bar after a short delay
        QTimer.singleShot(2000, lambda: self.progress_bar.setVisible(False))

        # Update last sync time if successful
        if success:
            last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.last_sync_label.setText(f"Last Sync: {last_sync}")

        # Show result message
        if success:
            QMessageBox.information(self, "Sync Complete", message)
        else:
            QMessageBox.warning(self, "Sync Failed", message)

    def save_settings(self):
        """Save settings and close dialog."""
        # Update config
        self.drive_sync.config['sync_enabled'] = self.enable_sync_checkbox.isChecked()
        self.drive_sync.config['sync_frequency'] = self.frequency_combo.currentData()

        # Save to file
        self.drive_sync.save_config()

        # Close dialog
        self.accept()
