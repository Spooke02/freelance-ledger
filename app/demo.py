"""Built-in sample freelancer payments (clearly fictional) so the app runs without PayPal keys."""
from .ledger import Txn

DEMO = [
    Txn("D1", "2026-04-12", "Northwind Studio (demo)", "USD", 400.00, 17.90, "Landing page design", inr_rate=83.5),
    Txn("D2", "2026-05-03", "Contoso Ltd (demo)", "USD", 850.00, 36.45, "Python data pipeline", inr_rate=83.4),
    Txn("D3", "2026-06-20", "Fabrikam (demo)", "EUR", 600.00, 25.10, "Sheets automation", inr_rate=90.2),
    Txn("D4", "2026-07-15", "Adventure Works (demo)", "USD", 1200.00, 51.00, "Website build + hosting setup", inr_rate=83.9),
    Txn("D5", "2026-08-08", "Tailspin Toys (demo)", "GBP", 300.00, 13.20, "Monthly retainer", inr_rate=105.1),
    Txn("D6", "2026-09-02", "Wide World Importers (demo)", "USD", 950.00, 40.60, "Dashboard + training", inr_rate=84.0),
    Txn("D7", "2026-10-05", "Litware (demo)", "USD", 500.00, 21.50, "Bug fixes", inr_rate=84.2),
]
