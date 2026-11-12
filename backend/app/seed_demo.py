from app.core.config import settings
from app.db.session import SessionLocal
from app.seed import seed_demo


def main() -> None:
    with SessionLocal() as db:
        seed_demo(db, settings.demo_password)
        db.commit()
    print("MemoryCare fictional demo data is ready.")
    print("Accounts: admin@memorycare.example.com, guardian@memorycare.example.com,")
    print("          meera.demo@memorycare.example.com, aarav.demo@memorycare.example.com")
    print("Password: value of DEMO_PASSWORD in backend/.env (change before shared use).")


if __name__ == "__main__":
    main()
