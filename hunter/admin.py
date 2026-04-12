from django.contrib import admin

from .models.models import BillingInvoice, BillingSubscription


@admin.register(BillingSubscription)
class BillingSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'owner',
        'plan_code',
        'billing_cycle',
        'status',
        'stripe_customer_id',
        'stripe_subscription_id',
        'price_amount',
        'currency',
        'auto_renew',
        'current_period_end',
    )
    list_filter = ('plan_code', 'billing_cycle', 'status', 'auto_renew')
    search_fields = (
        'owner__username',
        'owner__email',
        'stripe_customer_id',
        'stripe_subscription_id',
        'stripe_checkout_session_id',
    )


@admin.register(BillingInvoice)
class BillingInvoiceAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'owner',
        'plan_code',
        'billing_cycle',
        'status',
        'stripe_invoice_id',
        'amount',
        'currency',
        'issued_at',
        'paid_at',
    )
    list_filter = ('plan_code', 'billing_cycle', 'status')
    search_fields = (
        'owner__username',
        'owner__email',
        'external_reference',
        'stripe_invoice_id',
    )
