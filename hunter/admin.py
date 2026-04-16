from django.contrib import admin

from .models.models import BillingInvoice, BillingSubscription, ProductEvent


@admin.register(ProductEvent)
class ProductEventAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'event_name',
        'category',
        'owner',
        'source',
        'created_at',
    )
    list_filter = ('category', 'event_name', 'source', 'created_at')
    search_fields = ('event_name', 'source', 'owner__username', 'owner__email')
    readonly_fields = (
        'owner',
        'event_name',
        'category',
        'source',
        'metadata',
        'created_at',
        'updated_at',
    )


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
