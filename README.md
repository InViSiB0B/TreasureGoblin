# TreasureGoblin

**Your personal finance companion for tracking spending and building wealth through smarter money habits.**

TreasureGoblin helps you monitor your finances to create the financial future you deserve, whether that's next month or years from now. With an intuitive interface, powerful reporting tools, and cloud backup capabilities, managing your money has never been easier.

## Features

### Dashboard
- **Financial Summary** - View your total balance across all accounts at a glance
- **Month-to-Date Analysis** - Track current month income, expenses, and net balance
- **Month Comparison** - Compare current month metrics against the previous month
- **Recent Transactions** - Quick access to your latest financial activity
- **Nibble Assistant** - Your friendly financial advisor providing tips and guidance

### Transaction Management
- Add, edit, and delete income and expense transactions
- Filter transactions by month with an intuitive calendar selector
- Assign custom categories and optional tags for better organization
- View detailed transaction history with easy-to-read formatting

### Category System
- Create and manage custom income and expense categories
- Built-in system categories (Paycheck, Grocery, Housing, Transportation, and more)
- Separate management for income vs. expense categories
- Smart fallback system for uncategorized transactions

### Reports & Analytics
- Visual charts (pie and bar charts) for spending analysis
- Filter by custom date ranges, months, or years
- Toggle between expense and income reports
- Breakdown spending and income by category
- Data-driven insights to help you make better financial decisions

### Data Management & Backup
- Export your financial data as encrypted zip archives
- Import data from backups with merge or replace options
- Google Drive cloud sync with configurable frequency (manual, on close, daily, weekly, monthly)
- Secure OAuth2 authentication for cloud services
- Automatic backup creation with timestamps

## Technology Stack

- **GUI Framework:** PyQt5
- **Database:** SQLite3
- **Data Visualization:** Matplotlib with NumPy
- **Cloud Integration:** Google Drive API with OAuth2
- **Language:** Python 3

## Installation

### Prerequisites

- Python 3.7 or higher
- pip (Python package installer)

### Dependencies

Install the required packages:

```bash
pip install PyQt5 matplotlib numpy google-auth google-auth-oauthlib google-api-python-client
```

### Setup

1. Clone the repository:
```bash
git clone https://github.com/InViSiB0B/TreasureGoblin.git
cd TreasureGoblin
```

2. Run the application:
```bash
python main.py
```

On first run, TreasureGoblin will automatically create:
- Application directory: `~/.treasuregoblin/`
- Database file: `~/.treasuregoblin/treasuregoblin.db`
- Media directory: `~/.treasuregoblin/media/`

## Usage

### Getting Started

1. **Launch the application** by running `python main.py`
2. **Add your first transaction** in the Transactions tab
3. **Create custom categories** in the Categories tab to organize your finances
4. **View reports** in the Reports tab to analyze your spending patterns
5. **Monitor your progress** on the Dashboard

### Google Drive Sync (Optional)

To enable cloud backup:

1. Navigate to the Data Management tab
2. Click "Configure Google Drive Sync"
3. Authenticate with your Google account
4. Choose your preferred sync frequency
5. Your data will automatically backup to Google Drive

### Import/Export Data

- **Export:** Click "Export Database" in the Data Management tab to create a backup
- **Import:** Click "Import Database" and select a backup file to restore your data
  - Choose "Merge" to combine with existing data
  - Choose "Replace" to overwrite current data

## FAQ

### General

**Q: Where is my data stored?**
A: All data is stored locally in `~/.treasuregoblin/treasuregoblin.db` on your computer. If you enable Google Drive sync, encrypted backups are also stored in your Google Drive.

**Q: Is my financial data secure?**
A: Yes. Your data is stored locally on your machine in an SQLite database. Google Drive sync uses OAuth2 authentication and stores encrypted backups. TreasureGoblin never sends your data to any third-party servers except Google Drive (if you enable sync).

**Q: Can I use TreasureGoblin on multiple computers?**
A: Yes! Enable Google Drive sync on each computer to keep your financial data synchronized across devices.

### Troubleshooting

**Q: The application won't start. What should I do?**
A: Ensure all dependencies are installed correctly by running:
```bash
pip install --upgrade PyQt5 matplotlib numpy google-auth google-auth-oauthlib google-api-python-client
```

**Q: I accidentally deleted a transaction. Can I recover it?**
A: If you have a recent backup (via Export or Google Drive sync), you can import it to restore your data. Use the "Merge" option to avoid losing newer transactions.

**Q: How do I change the sync frequency for Google Drive?**
A: Go to Data Management > Configure Google Drive Sync and select your preferred frequency from the dropdown menu.

**Q: Can I edit system categories?**
A: System categories (like Paycheck, Grocery, Housing) cannot be edited or deleted to maintain data consistency. However, you can create as many custom categories as you need.

### Features

**Q: What's the difference between categories and tags?**
A: Categories are primary classifications (e.g., "Grocery", "Entertainment") that every transaction must have. Tags are optional labels you can add for additional organization (e.g., "vacation", "gift", "emergency").

**Q: How far back can I view my transaction history?**
A: TreasureGoblin stores all your transactions indefinitely. You can view and analyze data from any time period using the month/year selectors and custom date range filters.

**Q: What chart types are available in Reports?**
A: Reports currently support pie charts (showing percentage breakdown by category) and bar charts (showing amounts by category). You can toggle between income and expense views.

## Contributing

Contributions are welcome! If you'd like to contribute to TreasureGoblin:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Nibble the Goblin character for making personal finance fun and engaging
- The PyQt5 community for excellent documentation and support
- All contributors who help make TreasureGoblin better

---

**Start building your financial future today with TreasureGoblin!**
