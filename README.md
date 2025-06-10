# E-commerce API

A Django REST Framework ecommerce backend with Google OAuth2 login, JWT authentication, product catalogues, carts, orders, and reviews.

## Features

- Google OAuth2 login with JWT access and refresh tokens.
- Categories and products with search, filtering, ordering, and pagination.
- Authenticated carts and customer-specific orders.
- Stock validation and transactional stock reservation when adding order items.
- Review creation with one review per user and owner-only updates/deletes.

## Project layout

- `ecommerce/` — Django project settings and URL configuration.
- `login/` — custom user model, Google OAuth views, and authentication serializers.
- `products/` — product, cart, order, order-item, and review models, serializers, and API views.
- `git_Script.py` — commits and pushes changes with sequential commit dates.

## API routes

Product APIs are available under `/api/`:

- `/api/categories/`
- `/api/products/`
- `/api/carts/`
- `/api/carts/checkout/` — convert the authenticated user's cart into a pending order.
- `/api/orders/`
- `/api/orders/<id>/cancel/` — cancel a pending order and restore reserved stock.
- `/api/order-items/`
- `/api/reviews/`

Google OAuth endpoints:

- `/google/login/` — redirect to Google authorization.
- `/google/callback/` — exchange the authorization code for JWT tokens.

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Configure PostgreSQL and set the environment variables below.
4. Apply migrations and start the development server:

   ```bash
   python manage.py migrate
   python manage.py runserver
   ```

## Configuration

- `DJANGO_SECRET_KEY` — Django secret key; set this outside development.
- `DJANGO_DEBUG` — `True` or `False`.
- `DJANGO_ALLOWED_HOSTS` — comma-separated allowed hosts.
- `GOOGLE_REDIRECT_URI` — registered Google OAuth callback URL.

Orders begin with `pending` status and can be cancelled by their owner while
pending. Payment confirmation and shipping fulfillment are not yet integrated.

The Google provider credentials must also be configured through Django Allauth's `SocialApp` records.

## Checks

Compile the main Python modules with:

```bash
python -m py_compile login/views.py products/views.py products/models.py
```

Run Django checks after installing all dependencies:

```bash
python manage.py check
```
