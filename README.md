# ☕ Premium Cafe Portal — Django

## 🚀 Setup Commands (From Scratch)

```bash
# 1. Create & activate virtual environment
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Apply migrations
python manage.py makemigrations
python manage.py migrate

# 4. Create superuser (Admin - role=2)
python manage.py create_admin

# 5. Seed sample data (optional)
python manage.py seed_data

# 6. Run the server
python manage.py runserver
```

## 👤 User Roles
| Role | Value | Access |
|------|-------|--------|
| User | 1 | Browse menu, place orders, reviews, reservations, loyalty points |
| Admin | 2 | Full CRUD on products, categories, orders, users, analytics |

## 🌟 Advanced Features
- JWT-based session auth
- Loyalty Points system
- Table Reservations
- Real-time order tracking (status updates)
- Product ratings & reviews
- Category + attribute management
- Admin dashboard with analytics
- Low stock alerts
- Order history & invoices
- Coupon/discount system
