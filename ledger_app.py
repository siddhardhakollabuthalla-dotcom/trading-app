import sys
import json
import requests
import yfinance as yf
from datetime import datetime
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QStackedWidget, QTableWidget,
    QTableWidgetItem, QHeaderView, QDialog, QFormLayout, QDoubleSpinBox,
    QComboBox, QMessageBox, QFrame, QScrollArea, QGridLayout
)

# Firebase REST Auth & Firestore Config
FIREBASE_API_KEY = "AIzaSyBAkFU5JFcQL4jM2AsYkBnp9P_YeO0dwo8"
PROJECT_ID = "trading-app-66077"
AUTH_SIGNUP_URL = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={FIREBASE_API_KEY}"
AUTH_SIGNIN_URL = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
FIRESTORE_BASE = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents/users"

# Modern Dark Theme Stylesheet
STYLESHEET = """
QWidget {
    background-color: #0B0F14;
    color: #E8EDF2;
    font-family: 'Segoe UI', Inter, sans-serif;
    font-size: 13px;
}
QFrame#CardBox {
    background-color: #121820;
    border: 1px solid #212B36;
    border-radius: 10px;
    padding: 20px;
}
QLabel#BrandMark {
    background-color: #D4A73C;
    color: #0B0F14;
    font-weight: bold;
    font-size: 16px;
    border-radius: 6px;
    padding: 4px 8px;
}
QLabel#HeaderTitle {
    font-size: 22px;
    font-weight: bold;
    color: #E8EDF2;
}
QLabel#SubTitle {
    color: #7C8A99;
    font-size: 12px;
}
QLineEdit, QDoubleSpinBox, QComboBox {
    background-color: #0B0F14;
    border: 1px solid #212B36;
    border-radius: 6px;
    color: #E8EDF2;
    padding: 8px 12px;
    font-size: 13px;
}
QLineEdit:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border-color: #D4A73C;
}
QPushButton {
    background-color: #D4A73C;
    color: #14100A;
    font-weight: bold;
    border: none;
    border-radius: 6px;
    padding: 10px 16px;
}
QPushButton:hover {
    background-color: #E5B84C;
}
QPushButton#SecondaryBtn {
    background-color: transparent;
    color: #7C8A99;
    border: 1px solid #212B36;
}
QPushButton#SecondaryBtn:hover {
    color: #E8EDF2;
    border-color: #D4A73C;
}
QPushButton#NavBtn {
    background-color: transparent;
    color: #7C8A99;
    border: none;
    padding: 8px 14px;
    font-weight: 600;
}
QPushButton#NavBtn:hover {
    color: #E8EDF2;
}
QPushButton#NavBtn[active="true"] {
    color: #D4A73C;
    border-bottom: 2px solid #D4A73C;
}
QTableWidget {
    background-color: #121820;
    border: 1px solid #212B36;
    gridline-color: #212B36;
    border-radius: 8px;
}
QHeaderView::section {
    background-color: #171F29;
    color: #7C8A99;
    padding: 6px;
    border: 1px solid #212B36;
    font-weight: bold;
    text-transform: uppercase;
}
"""

class StockQuoteWorker(QThread):
    quotes_ready = pyqtSignal(dict)

    def __init__(self, symbols):
        super().__init__()
        self.symbols = symbols

    def run(self):
        results = {}
        for sym in self.symbols:
            try:
                ticker = yf.Ticker(sym)
                fast = ticker.fast_info
                price = fast.last_price
                prev = fast.previous_close
                change = price - prev if (price and prev) else 0.0
                pct = (change / prev * 100) if prev else 0.0
                results[sym] = {
                    "price": price or 0.0,
                    "change": change,
                    "pct": pct
                }
            except Exception:
                results[sym] = {"price": 0.0, "change": 0.0, "pct": 0.0}
        self.quotes_ready.emit(results)

class LedgerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ledger — Stock Investment & Trading Journal")
        self.resize(1100, 750)
        self.setStyleSheet(STYLESHEET)

        # App State
        self.id_token = None
        self.local_id = None
        self.email = None
        self.balance = 0.0
        self.investments = []  # [{symbol, shares, buyPrice, id}]
        self.watchlist = []    # [{symbol, name, id}]
        self.journal_entries = [] # [{id, date, symbol, type, price, shares, pnl, note}]
        self.challenges = []   # [{id, startCapital, targetCapital, startDate}]

        self.init_ui()

    def init_ui(self):
        self.central_widget = QStackedWidget()
        self.setCentralWidget(self.central_widget)

        self.create_auth_view()
        self.create_main_view()

        self.central_widget.addWidget(self.auth_page)
        self.central_widget.addWidget(self.main_page)

        self.central_widget.setCurrentWidget(self.auth_page)

    # ---------------- Auth View ----------------
    def create_auth_view(self):
        self.auth_page = QWidget()
        layout = QVBoxLayout(self.auth_page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QFrame()
        card.setObjectName("CardBox")
        card.setFixedWidth(360)
        card_layout = QVBoxLayout(card)

        brand_layout = QHBoxLayout()
        mark = QLabel("L")
        mark.setObjectName("BrandMark")
        brand_name = QLabel("Ledger")
        brand_name.setStyleSheet("font-size: 20px; font-weight: bold;")
        brand_layout.addWidget(mark)
        brand_layout.addWidget(brand_name)
        brand_layout.addStretch()
        card_layout.addLayout(brand_layout)

        self.auth_title = QLabel("Sign In")
        self.auth_title.setObjectName("HeaderTitle")
        card_layout.addWidget(self.auth_title)

        self.auth_sub = QLabel("Access your stock investments & trading journal")
        self.auth_sub.setObjectName("SubTitle")
        card_layout.addWidget(self.auth_sub)
        card_layout.addSpacing(10)

        card_layout.addWidget(QLabel("EMAIL"))
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("user@example.com")
        card_layout.addWidget(self.email_input)

        card_layout.addWidget(QLabel("PASSWORD"))
        self.pass_input = QLineEdit()
        self.pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pass_input.setPlaceholderText("••••••••")
        card_layout.addWidget(self.pass_input)

        self.auth_btn = QPushButton("Sign In")
        self.auth_btn.clicked.connect(self.handle_auth)
        card_layout.addWidget(self.auth_btn)

        self.toggle_auth_btn = QPushButton("Don't have an account? Sign Up")
        self.toggle_auth_btn.setObjectName("SecondaryBtn")
        self.toggle_auth_btn.clicked.connect(self.toggle_auth_mode)
        card_layout.addWidget(self.toggle_auth_btn)

        self.is_signup_mode = False

        layout.addWidget(card)

    def toggle_auth_mode(self):
        self.is_signup_mode = not self.is_signup_mode
        if self.is_signup_mode:
            self.auth_title.setText("Create Account")
            self.auth_btn.setText("Sign Up")
            self.toggle_auth_btn.setText("Already have an account? Sign In")
        else:
            self.auth_title.setText("Sign In")
            self.auth_btn.setText("Sign In")
            self.toggle_auth_btn.setText("Don't have an account? Sign Up")

    def handle_auth(self):
        email = self.email_input.text().strip()
        password = self.pass_input.text().strip()
        if not email or not password:
            QMessageBox.warning(self, "Error", "Please fill in all credentials.")
            return

        url = AUTH_SIGNUP_URL if self.is_signup_mode else AUTH_SIGNIN_URL
        payload = {"email": email, "password": password, "returnSecureToken": True}
        try:
            res = requests.post(url, json=payload).json()
            if "error" in res:
                err_msg = res["error"]["message"]
                if "CONFIGURATION_NOT_FOUND" in err_msg or "OPERATION_NOT_ALLOWED" in err_msg:
                    QMessageBox.critical(
                        self,
                        "Firebase Auth Setup Required",
                        "Firebase Email/Password Authentication is not enabled yet in your Firebase Console.\n\n"
                        "To fix this:\n"
                        "1. Go to https://console.firebase.google.com/\n"
                        "2. Select your project 'trading-app-66077'\n"
                        "3. Click 'Authentication' -> 'Get Started'\n"
                        "4. Enable 'Email/Password' under Sign-in method tab."
                    )
                else:
                    QMessageBox.critical(self, "Auth Error", err_msg)
                return

            self.id_token = res["idToken"]
            self.local_id = res["localId"]
            self.email = email
            self.load_user_data()
            self.central_widget.setCurrentWidget(self.main_page)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to authenticate: {str(e)}")

    # ---------------- Main Dashboard View ----------------
    def create_main_view(self):
        self.main_page = QWidget()
        main_layout = QVBoxLayout(self.main_page)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Top Bar
        top_bar = QFrame()
        top_bar.setStyleSheet("background-color: #121820; border-bottom: 1px solid #212B36;")
        tb_layout = QHBoxLayout(top_bar)
        tb_layout.setContentsMargins(20, 10, 20, 10)

        mark = QLabel("L")
        mark.setObjectName("BrandMark")
        title = QLabel("Ledger")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        tb_layout.addWidget(mark)
        tb_layout.addWidget(title)

        tb_layout.addSpacing(30)

        self.btn_nav_invest = QPushButton("Investments Portfolio")
        self.btn_nav_invest.setObjectName("NavBtn")
        self.btn_nav_invest.setProperty("active", True)
        self.btn_nav_invest.clicked.connect(lambda: self.switch_tab(0))

        self.btn_nav_journal = QPushButton("Trading Journal & P&L")
        self.btn_nav_journal.setObjectName("NavBtn")
        self.btn_nav_journal.clicked.connect(lambda: self.switch_tab(1))

        self.btn_nav_challenge = QPushButton("Challenges")
        self.btn_nav_challenge.setObjectName("NavBtn")
        self.btn_nav_challenge.clicked.connect(lambda: self.switch_tab(2))

        tb_layout.addWidget(self.btn_nav_invest)
        tb_layout.addWidget(self.btn_nav_journal)
        tb_layout.addWidget(self.btn_nav_challenge)
        tb_layout.addStretch()

        self.user_lbl = QLabel()
        self.user_lbl.setStyleSheet("color: #7C8A99;")
        logout_btn = QPushButton("Logout")
        logout_btn.setObjectName("SecondaryBtn")
        logout_btn.clicked.connect(self.logout)

        tb_layout.addWidget(self.user_lbl)
        tb_layout.addWidget(logout_btn)

        main_layout.addWidget(top_bar)

        # Tab Stack Widget
        self.tabs_stack = QStackedWidget()

        self.tab_investments = self.build_investments_tab()
        self.tab_journal = self.build_journal_tab()
        self.tab_challenges = self.build_challenges_tab()

        self.tabs_stack.addWidget(self.tab_investments)
        self.tabs_stack.addWidget(self.tab_journal)
        self.tabs_stack.addWidget(self.tab_challenges)

        main_layout.addWidget(self.tabs_stack)

    def switch_tab(self, index):
        self.tabs_stack.setCurrentIndex(index)
        self.btn_nav_invest.setProperty("active", index == 0)
        self.btn_nav_journal.setProperty("active", index == 1)
        self.btn_nav_challenge.setProperty("active", index == 2)

        for btn in [self.btn_nav_invest, self.btn_nav_journal, self.btn_nav_challenge]:
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def logout(self):
        self.id_token = None
        self.local_id = None
        self.central_widget.setCurrentWidget(self.auth_page)

    # ---------------- Tab 1: Investments & Watchlist ----------------
    def build_investments_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)

        # Balance Header Row
        header_card = QFrame()
        header_card.setObjectName("CardBox")
        h_layout = QHBoxLayout(header_card)

        v1 = QVBoxLayout()
        sub1 = QLabel("TOTAL ACCOUNT VALUE")
        sub1.setObjectName("SubTitle")
        v1.addWidget(sub1)
        self.lbl_total_val = QLabel("₹0.00")
        self.lbl_total_val.setStyleSheet("font-size: 24px; font-weight: bold; color: #D4A73C;")
        v1.addWidget(self.lbl_total_val)
        h_layout.addLayout(v1)

        v2 = QVBoxLayout()
        sub2 = QLabel("AVAILABLE CASH CAPITAL")
        sub2.setObjectName("SubTitle")
        v2.addWidget(sub2)
        self.lbl_cash_bal = QLabel("₹0.00")
        self.lbl_cash_bal.setStyleSheet("font-size: 24px; font-weight: bold;")
        v2.addWidget(self.lbl_cash_bal)
        h_layout.addLayout(v2)

        set_cap_btn = QPushButton("Set Capital")
        set_cap_btn.setObjectName("SecondaryBtn")
        set_cap_btn.clicked.connect(self.open_capital_dialog)
        h_layout.addWidget(set_cap_btn)

        layout.addWidget(header_card)

        # Table & Actions Bar
        actions_bar = QHBoxLayout()
        sec_title = QLabel("Invested Stocks")
        sec_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        actions_bar.addWidget(sec_title)
        actions_bar.addStretch()

        add_stock_btn = QPushButton("+ Add Stock Investment")
        add_stock_btn.clicked.connect(self.open_add_stock_dialog)
        refresh_btn = QPushButton("🔄 Refresh Live Quotes")
        refresh_btn.setObjectName("SecondaryBtn")
        refresh_btn.clicked.connect(self.fetch_live_quotes)

        actions_bar.addWidget(add_stock_btn)
        actions_bar.addWidget(refresh_btn)
        layout.addLayout(actions_bar)

        self.stock_table = QTableWidget(0, 7)
        self.stock_table.setHorizontalHeaderLabels([
            "Symbol", "Shares", "Avg Buy Price", "Current Price", "Market Value", "Unrealized P&L", "Actions"
        ])
        self.stock_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.stock_table)

        return widget

    # ---------------- Tab 2: Journal & P&L Log ----------------
    def build_journal_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)

        actions_bar = QHBoxLayout()
        title = QLabel("Trading Journal & Closed Trades")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        actions_bar.addWidget(title)
        actions_bar.addStretch()

        add_journal_btn = QPushButton("+ Log New Trade Entry")
        add_journal_btn.clicked.connect(self.open_add_journal_dialog)
        actions_bar.addWidget(add_journal_btn)
        layout.addLayout(actions_bar)

        self.journal_table = QTableWidget(0, 8)
        self.journal_table.setHorizontalHeaderLabels([
            "Date", "Symbol", "Type", "Price", "Shares", "Realized P&L", "Notes", "Actions"
        ])
        self.journal_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.journal_table)

        return widget

    # ---------------- Tab 3: Challenges ----------------
    def build_challenges_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)

        actions_bar = QHBoxLayout()
        title = QLabel("Capital Growth Challenges")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        actions_bar.addWidget(title)
        actions_bar.addStretch()

        add_ch_btn = QPushButton("+ Add New Challenge")
        add_ch_btn.clicked.connect(self.open_add_challenge_dialog)
        actions_bar.addWidget(add_ch_btn)
        layout.addLayout(actions_bar)

        self.challenges_scroll = QScrollArea()
        self.challenges_scroll.setWidgetResizable(True)
        self.challenges_container = QWidget()
        self.challenges_layout = QVBoxLayout(self.challenges_container)
        self.challenges_scroll.setWidget(self.challenges_container)

        layout.addWidget(self.challenges_scroll)

        return widget

    # ---------------- Firebase Data Sync ----------------
    def load_user_data(self):
        self.user_lbl.setText(self.email)
        try:
            res = requests.get(f"{FIRESTORE_BASE}/{self.local_id}?key={FIREBASE_API_KEY}").json()
            if "fields" in res:
                fields = res["fields"]
                self.balance = float(fields.get("balance", {}).get("doubleValue", 0.0))
                
                # Decode JSON strings stored in Firestore
                inv_str = fields.get("investments", {}).get("stringValue", "[]")
                j_str = fields.get("journal", {}).get("stringValue", "[]")
                ch_str = fields.get("challenges", {}).get("stringValue", "[]")

                self.investments = json.loads(inv_str)
                self.journal_entries = json.loads(j_str)
                self.challenges = json.loads(ch_str)
            else:
                # Initialize document
                self.save_user_data()
        except Exception as e:
            print("Error loading user data:", e)

        self.update_ui()
        self.fetch_live_quotes()

    def save_user_data(self):
        payload = {
            "fields": {
                "email": {"stringValue": self.email or ""},
                "balance": {"doubleValue": float(self.balance)},
                "investments": {"stringValue": json.dumps(self.investments)},
                "journal": {"stringValue": json.dumps(self.journal_entries)},
                "challenges": {"stringValue": json.dumps(self.challenges)}
            }
        }
        try:
            update_mask = "updateMask.fieldPaths=email&updateMask.fieldPaths=balance&updateMask.fieldPaths=investments&updateMask.fieldPaths=journal&updateMask.fieldPaths=challenges"
            url = f"{FIRESTORE_BASE}/{self.local_id}?key={FIREBASE_API_KEY}&{update_mask}"
            headers = {"Authorization": f"Bearer {self.id_token}"} if self.id_token else {}
            res = requests.patch(url, json=payload, headers=headers)
            if res.status_code != 200:
                requests.patch(url, json=payload)
        except Exception as e:
            print("Error saving to Firestore:", e)

    def update_ui(self):
        self.lbl_cash_bal.setText(f"₹{self.balance:,.2f}")
        self.refresh_stock_table({})
        self.refresh_journal_table()
        self.refresh_challenges_list()

    # ---------------- Stock Live Updates ----------------
    def fetch_live_quotes(self):
        symbols = list(set([inv["symbol"].upper() for inv in self.investments]))
        if not symbols:
            self.refresh_stock_table({})
            return
        self.worker = StockQuoteWorker(symbols)
        self.worker.quotes_ready.connect(self.refresh_stock_table)
        self.worker.start()

    def refresh_stock_table(self, quotes):
        self.stock_table.setRowCount(0)
        total_market_val = self.balance

        for idx, inv in enumerate(self.investments):
            sym = inv["symbol"].upper()
            shares = float(inv["shares"])
            buy_price = float(inv["buyPrice"])

            q = quotes.get(sym, {"price": buy_price, "change": 0.0, "pct": 0.0})
            curr_price = q["price"] if q["price"] > 0 else buy_price

            mkt_val = shares * curr_price
            pnl = (curr_price - buy_price) * shares
            total_market_val += mkt_val

            self.stock_table.insertRow(idx)
            self.stock_table.setItem(idx, 0, QTableWidgetItem(sym))
            self.stock_table.setItem(idx, 1, QTableWidgetItem(f"{shares:,.2f}"))
            self.stock_table.setItem(idx, 2, QTableWidgetItem(f"₹{buy_price:,.2f}"))
            self.stock_table.setItem(idx, 3, QTableWidgetItem(f"₹{curr_price:,.2f}"))
            self.stock_table.setItem(idx, 4, QTableWidgetItem(f"₹{mkt_val:,.2f}"))

            pnl_item = QTableWidgetItem(f"{'+' if pnl>=0 else ''}₹{pnl:,.2f}")
            pnl_item.setForeground(Qt.GlobalColor.green if pnl >= 0 else Qt.GlobalColor.red)
            self.stock_table.setItem(idx, 5, pnl_item)

            btn_container = QWidget()
            btn_layout = QHBoxLayout(btn_container)
            btn_layout.setContentsMargins(0, 0, 0, 0)
            btn_layout.setSpacing(4)

            edit_btn = QPushButton("Edit")
            edit_btn.setStyleSheet("background-color: #D4A73C; color: #14100A; padding: 4px;")
            edit_btn.clicked.connect(lambda _, i=idx: self.open_add_stock_dialog(i))

            del_btn = QPushButton("Delete")
            del_btn.setStyleSheet("background-color: #EF4444; color: white; padding: 4px;")
            del_btn.clicked.connect(lambda _, i=idx: self.delete_investment(i))

            btn_layout.addWidget(edit_btn)
            btn_layout.addWidget(del_btn)
            self.stock_table.setCellWidget(idx, 6, btn_container)

        self.lbl_total_val.setText(f"₹{total_market_val:,.2f}")

    def refresh_journal_table(self):
        self.journal_table.setRowCount(0)
        for idx, entry in enumerate(self.journal_entries):
            self.journal_table.insertRow(idx)
            self.journal_table.setItem(idx, 0, QTableWidgetItem(entry.get("date", "")))
            self.journal_table.setItem(idx, 1, QTableWidgetItem(entry.get("symbol", "").upper()))
            self.journal_table.setItem(idx, 2, QTableWidgetItem(entry.get("type", "BUY")))
            self.journal_table.setItem(idx, 3, QTableWidgetItem(f"₹{entry.get('price', 0):,.2f}"))
            self.journal_table.setItem(idx, 4, QTableWidgetItem(str(entry.get("shares", 0))))

            pnl = float(entry.get("pnl", 0.0))
            pnl_item = QTableWidgetItem(f"{'+' if pnl>=0 else ''}₹{pnl:,.2f}")
            pnl_item.setForeground(Qt.GlobalColor.green if pnl >= 0 else Qt.GlobalColor.red)
            self.journal_table.setItem(idx, 5, pnl_item)

            self.journal_table.setItem(idx, 6, QTableWidgetItem(entry.get("note", "")))

            del_btn = QPushButton("Delete")
            del_btn.setStyleSheet("background-color: #EF4444; color: white; padding: 4px;")
            del_btn.clicked.connect(lambda _, i=idx: self.delete_journal_entry(i))
            self.journal_table.setCellWidget(idx, 7, del_btn)

    def refresh_challenges_list(self):
        # Clear existing items
        for i in reversed(range(self.challenges_layout.count())):
            self.challenges_layout.itemAt(i).widget().setParent(None)

        for ch in self.challenges:
            card = QFrame()
            card.setObjectName("CardBox")
            c_layout = QVBoxLayout(card)

            start = float(ch["startCapital"])
            target = float(ch["targetCapital"])
            current = self.balance

            reached = current >= target
            pct = min(100.0, max(0.0, ((current - start) / (target - start)) * 100)) if target > start else 100.0

            title = QLabel(f"Challenge Target: ₹{target:,.2f}")
            title.setStyleSheet("font-weight: bold; font-size: 16px;")
            prog = QLabel(f"Progress: {pct:.1f}% (₹{current:,.2f} / ₹{target:,.2f})")
            status = QLabel("Status: COMPLETED 🎉" if reached else "Status: IN PROGRESS 📈")
            status.setStyleSheet("color: #22C55E;" if reached else "color: #D4A73C;")

            c_layout.addWidget(title)
            c_layout.addWidget(prog)
            c_layout.addWidget(status)
            self.challenges_layout.addWidget(card)

        self.challenges_layout.addStretch()

    # ---------------- Dialog Handlers ----------------
    def open_capital_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Set Starting Cash Capital")
        layout = QFormLayout(dlg)

        spin = QDoubleSpinBox()
        spin.setMaximum(1000000000.0)
        spin.setValue(self.balance)
        layout.addRow("Cash Capital (₹):", spin)

        btn = QPushButton("Save")
        btn.clicked.connect(lambda: self.save_capital(spin.value(), dlg))
        layout.addRow(btn)
        dlg.exec()

    def save_capital(self, val, dlg):
        self.balance = val
        self.save_user_data()
        self.update_ui()
        dlg.accept()

    def open_add_stock_dialog(self, edit_idx=None):
        dlg = QDialog(self)
        is_edit = edit_idx is not None
        inv = self.investments[edit_idx] if is_edit else None

        dlg.setWindowTitle("Edit Stock Investment" if is_edit else "Add Stock Investment")
        layout = QFormLayout(dlg)

        sym_input = QLineEdit()
        sym_input.setText(inv["symbol"] if is_edit else "")
        sym_input.setPlaceholderText("e.g. AAPL, NVDA, TSLA")

        shares_spin = QDoubleSpinBox()
        shares_spin.setMaximum(1000000.0)
        shares_spin.setValue(float(inv["shares"]) if is_edit else 0.0)

        price_spin = QDoubleSpinBox()
        price_spin.setMaximum(1000000.0)
        price_spin.setValue(float(inv["buyPrice"]) if is_edit else 0.0)

        status_combo = QComboBox()
        status_combo.addItems(["Holding (Active Investment)", "Closed Trade — Profit 🟢", "Closed Trade — Loss 🔴"])

        if is_edit:
            st = inv.get("status", "holding")
            status_combo.setCurrentIndex(1 if st == "profit" else (2 if st == "loss" else 0))

        pnl_spin = QDoubleSpinBox()
        pnl_spin.setMaximum(10000000.0)
        pnl_spin.setMinimum(0.0)
        pnl_spin.setValue(abs(inv.get("manualPnl", 0.0)) if is_edit else 0.0)

        layout.addRow("Stock Symbol:", sym_input)
        layout.addRow("Shares:", shares_spin)
        layout.addRow("Buy Price (₹):", price_spin)
        layout.addRow("Status / Result:", status_combo)
        layout.addRow("Profit / Loss Amount (₹):", pnl_spin)

        btn = QPushButton("Update Investment" if is_edit else "Add Investment")
        btn.clicked.connect(lambda: self.save_stock(
            sym_input.text(), shares_spin.value(), price_spin.value(),
            status_combo.currentIndex(), pnl_spin.value(), edit_idx, dlg
        ))
        layout.addRow(btn)
        dlg.exec()

    def save_stock(self, symbol, shares, price, status_idx, pnl_amount, edit_idx, dlg):
        if not symbol or shares <= 0 or price <= 0:
            QMessageBox.warning(self, "Error", "Valid symbol, shares, and price required.")
            return

        status = "holding"
        if status_idx == 1:
            status = "profit"
        elif status_idx == 2:
            status = "loss"

        pnl_val = 0.0
        if status in ["profit", "loss"]:
            pnl_val = pnl_amount if status == "profit" else -pnl_amount

            # If editing existing item, deduct old manual PnL impact
            if edit_idx is not None and "manualPnl" in self.investments[edit_idx]:
                self.balance -= float(self.investments[edit_idx]["manualPnl"])

            # Auto-log into Journal & update balance
            self.journal_entries.append({
                "id": str(int(datetime.now().timestamp() * 1000)),
                "date": datetime.now().strftime("%Y-%m-%d"),
                "symbol": symbol.upper(),
                "type": "SELL (PROFIT)" if status == "profit" else "SELL (LOSS)",
                "price": price,
                "shares": shares,
                "pnl": pnl_val,
                "note": f"Stock investment result: {'+' if status=='profit' else ''}₹{pnl_val:,.2f}"
            })
            self.balance += pnl_val

        item_data = {
            "id": self.investments[edit_idx]["id"] if edit_idx is not None else str(int(datetime.now().timestamp() * 1000)),
            "symbol": symbol.upper(),
            "shares": shares,
            "buyPrice": price,
            "status": status,
            "manualPnl": pnl_val
        }

        if edit_idx is not None:
            self.investments[edit_idx] = item_data
        else:
            self.investments.append(item_data)

        self.save_user_data()
        self.update_ui()
        self.fetch_live_quotes()
        dlg.accept()

    def delete_investment(self, idx):
        del self.investments[idx]
        self.save_user_data()
        self.fetch_live_quotes()

    def open_add_journal_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Log Trade Entry")
        layout = QFormLayout(dlg)

        sym_input = QLineEdit()
        type_combo = QComboBox()
        type_combo.addItems(["BUY", "SELL"])
        price_spin = QDoubleSpinBox()
        price_spin.setMaximum(1000000.0)
        shares_spin = QDoubleSpinBox()
        shares_spin.setMaximum(1000000.0)
        pnl_spin = QDoubleSpinBox()
        pnl_spin.setMinimum(-1000000.0)
        pnl_spin.setMaximum(1000000.0)
        note_input = QLineEdit()

        layout.addRow("Symbol:", sym_input)
        layout.addRow("Type:", type_combo)
        layout.addRow("Price (₹):", price_spin)
        layout.addRow("Shares:", shares_spin)
        layout.addRow("Realized P&L (₹):", pnl_spin)
        layout.addRow("Notes:", note_input)

        btn = QPushButton("Save Entry")
        btn.clicked.connect(lambda: self.save_journal(
            sym_input.text(), type_combo.currentText(), price_spin.value(),
            shares_spin.value(), pnl_spin.value(), note_input.text(), dlg
        ))
        layout.addRow(btn)
        dlg.exec()

    def save_journal(self, symbol, ttype, price, shares, pnl, note, dlg):
        self.journal_entries.append({
            "id": str(int(datetime.now().timestamp() * 1000)),
            "date": datetime.now().strftime("%Y-%m-%d"),
            "symbol": symbol,
            "type": ttype,
            "price": price,
            "shares": shares,
            "pnl": pnl,
            "note": note
        })
        self.balance += pnl
        self.save_user_data()
        self.update_ui()
        dlg.accept()

    def delete_journal_entry(self, idx):
        pnl = float(self.journal_entries[idx].get("pnl", 0.0))
        self.balance -= pnl
        del self.journal_entries[idx]
        self.save_user_data()
        self.update_ui()

    def open_add_challenge_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Add Challenge")
        layout = QFormLayout(dlg)

        target_spin = QDoubleSpinBox()
        target_spin.setMaximum(1000000000.0)
        target_spin.setValue(self.balance * 1.5 if self.balance > 0 else 1000.0)

        layout.addRow("Target Capital (₹):", target_spin)

        btn = QPushButton("Create Challenge")
        btn.clicked.connect(lambda: self.save_challenge(target_spin.value(), dlg))
        layout.addRow(btn)
        dlg.exec()

    def save_challenge(self, target, dlg):
        self.challenges.append({
            "id": str(int(datetime.now().timestamp() * 1000)),
            "startCapital": self.balance,
            "targetCapital": target,
            "startDate": datetime.now().strftime("%Y-%m-%d")
        })
        self.save_user_data()
        self.update_ui()
        dlg.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LedgerApp()
    window.show()
    sys.exit(app.exec())
