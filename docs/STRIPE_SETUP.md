# Stripe Subscription Setup Guide

This document outlines the steps required to activate the Stripe payment system for BookGPT.

## 1. Stripe Dashboard Configuration

1.  **Create a Stripe Account:** Sign up at [stripe.com](https://stripe.com).
2.  **Get API Keys:**
    *   Go to **Developers > API Keys**.
    *   Copy the **Publishable key** (starts with `pk_test_`).
    *   Copy the **Secret key** (starts with `sk_test_`).
3.  **Create a Product:**
    *   Go to **Product Catalog > Add Product**.
    *   Name it "BookGPT Pro".
    *   Set a **Recurring price** (e.g., $20/month).
    *   Save the product and copy the **Price ID** (starts with `price_`).

## 2. Environment Variables

Open the `.env` file in the project root and update the following values:

```env
STRIPE_PUBLIC_KEY=pk_test_your_key_here
STRIPE_SECRET_KEY=sk_test_your_key_here
STRIPE_PRICE_ID=price_your_id_here
STRIPE_WEBHOOK_SECRET=whsec_your_secret_here (See step 3)
DOMAIN=http://localhost:6748
```

## 3. Webhook Setup (Local Testing)

To handle successful payments locally, you need the Stripe CLI to forward events to your app.

1.  **Install Stripe CLI:** `brew install stripe/stripe-cli/stripe` (on macOS).
2.  **Login:** `stripe login`
3.  **Listen for events:**
    ```bash
    stripe listen --forward-to localhost:6748/webhook
    ```
4.  **Copy Webhook Secret:** The CLI will output a "webhook signing secret" (starts with `whsec_`). Copy this into your `.env` file as `STRIPE_WEBHOOK_SECRET`.

## 4. Testing the Flow

1.  Start the app: `python app.py`.
2.  Log in as `hamish`.
3.  Go to the **Profile** page.
4.  Click **Subscribe Now**.
5.  Use a Stripe test card (e.g., `4242 4242 4242 4242`) to complete the checkout.
6.  Upon return, your profile should show **Pro Plan Active**.

## 5. Production Deployment

When moving to production:
1.  Toggle "Test Mode" off in the Stripe Dashboard.
2.  Update `.env` with live keys.
3.  Set up a formal Webhook Endpoint in the Stripe Dashboard pointing to `https://yourdomain.com/webhook`.
