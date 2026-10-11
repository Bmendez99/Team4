from django.contrib import admin

from .models import Category, MenuItem, Order, OrderItem


class MenuItemInline(admin.TabularInline):
    model = MenuItem
    extra = 1


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "display_order")
    ordering = ("display_order", "name")
    inlines = [MenuItemInline]


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price", "is_available")
    list_filter = ("category", "is_available")
    search_fields = ("name", "description")


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "customer_name", "customer_phone", "status", "total", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("customer_name", "customer_phone", "customer_email")
    inlines = [OrderItemInline]
