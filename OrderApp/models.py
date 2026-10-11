from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class MenuItem(models.Model):
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="items"
    )
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    image = models.ImageField(
        upload_to="menu_images/",
        blank=True,
        null=True
    )
    price = models.DecimalField(max_digits=6, decimal_places=2)
    is_available = models.BooleanField(default=True)

    class Meta:
        ordering = ["category__display_order", "name"]

    def __str__(self):
        return f"{self.name} ({self.category.name})"


class Cart(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cart"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    @classmethod
    def get_for_user(cls, user):
        cart, _ = cls.objects.get_or_create(user=user)
        return cart

    def get_total(self):
        return sum(
            (item.get_total() for item in self.cartitem_set.all()),
            start=0
        )

    def __str__(self):
        return f"Cart({self.user.username})"


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE)
    item = models.ForeignKey(MenuItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ("cart", "item")

    def get_total(self):
        return self.item.price * self.quantity

    def __str__(self):
        return f"{self.quantity} x {self.item.name}"

class Order(models.Model):
    """An order placed at checkout. Staff move it through the statuses below."""

    class Status(models.TextChoices):
        NEW = "new", "New"
        PREPARING = "preparing", "Preparing"
        READY = "ready", "Ready for pickup"
        COMPLETED = "completed", "Picked up"
        CANCELLED = "cancelled", "Cancelled"

    # Which status each status is allowed to move to.
    TRANSITIONS = {
        Status.NEW: {Status.PREPARING, Status.CANCELLED},
        Status.PREPARING: {Status.READY, Status.CANCELLED},
        Status.READY: {Status.COMPLETED},
        Status.COMPLETED: set(),
        Status.CANCELLED: set(),
    }
    ACTIVE_STATUSES = [Status.NEW, Status.PREPARING, Status.READY]

    TAX_RATE = Decimal("0.07")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders"
    )
    customer_name = models.CharField(max_length=100)
    customer_phone = models.CharField(max_length=30)
    customer_email = models.EmailField(blank=True)
    order_type = models.CharField(max_length=20, default="pickup")
    notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NEW,
        db_index=True
    )
    subtotal = models.DecimalField(max_digits=8, decimal_places=2)
    tax = models.DecimalField(max_digits=8, decimal_places=2)
    total = models.DecimalField(max_digits=8, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Order #{self.pk} - {self.customer_name} ({self.get_status_display()})"

    def can_move_to(self, new_status):
        return new_status in self.TRANSITIONS.get(self.status, set())

    @classmethod
    def create_from_cart(cls, cart, **customer_info):
        """Turn a cart into an order, using current menu prices, then empty the cart."""
        cart_items = list(cart.cartitem_set.select_related("item"))
        subtotal = sum((ci.get_total() for ci in cart_items), Decimal("0.00"))
        tax = (subtotal * cls.TAX_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        order = cls.objects.create(
            user=cart.user,
            subtotal=subtotal,
            tax=tax,
            total=subtotal + tax,
            **customer_info
        )
        OrderItem.objects.bulk_create([
            OrderItem(
                order=order,
                menu_item=ci.item,
                name=ci.item.name,
                unit_price=ci.item.price,
                quantity=ci.quantity,
            )
            for ci in cart_items
        ])
        cart.cartitem_set.all().delete()
        return order

    def to_dict(self):
        """Data the staff orders page needs for one ticket."""
        return {
            "id": self.pk,
            "customer_name": self.customer_name,
            "customer_phone": self.customer_phone,
            "notes": self.notes,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "items": [
                {"name": i.name, "qty": i.quantity}
                for i in self.items.all()
            ],
            "total": str(self.total),
        }


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    # Kept if the menu item is later deleted; name and price are copied so
    # old orders don't change when the menu does.
    menu_item = models.ForeignKey(MenuItem, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=150)
    unit_price = models.DecimalField(max_digits=6, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)

    def get_total(self):
        return self.unit_price * self.quantity

    def __str__(self):
        return f"{self.quantity} x {self.name}"
