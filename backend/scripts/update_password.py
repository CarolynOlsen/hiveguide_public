import getpass
from backend.main import SessionLocal, User
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def main():
    email = input("Enter user email to update: ").strip()
    password = getpass.getpass("Enter new password: ").strip()
    if not email or not password:
        print("Email and password are required.")
        return
    db = SessionLocal()
    user = db.query(User).filter(User.email == email).first()
    if user:
        user.password_hash = pwd_context.hash(password)
        db.commit()
        print(f"Password updated for {email}!")
    else:
        print("User not found.")
    db.close()

if __name__ == "__main__":
    main()