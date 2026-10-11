import json
from datetime import timedelta
from functools import wraps

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.views import LoginView, redirect_to_login
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .models import Cart, CartItem, Category, MenuItem, Order


def index(request):
    return render(request, "home.html")


def menu(request):
    categories = Category.objects.prefetch_related("items").all()
    return render(request, "menu.html", {"categories": categories})


def menu_item_detail(request, pk):
    item = get_object_or_404(MenuItem, pk=pk)
    return render(request, "menu_item_detail.html", {"item": item})


@login_required
def add_to_cart(request, item_id):
    item = get_object_or_404(MenuItem, pk=item_id, is_available=True)
    cart = Cart.get_for_user(request.user)
    cart_item, created = CartItem.objects.get_or_create(cart=cart, item=item)
    if not created:
        cart_item.quantity += 1
        cart_item.save()
    return redirect("cart")


class CustomLoginView(LoginView):
    template_name = "login.html"


def register(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("index")
    else:
        form = UserCreationForm()
    return render(request, "register.html", {"form": form})


@login_required
def cart(request):
    cart = Cart.get_for_user(request.user)
    return render(request, "cart.html", {"cart": cart})


@login_required
@require_POST
def update_cart_item(request, cart_item_id):
    cart_item = get_object_or_404(CartItem, pk=cart_item_id, cart__user=request.user)
    quantity = int(request.POST.get("quantity", cart_item.quantity))
    if quantity < 1:
        cart_item.delete()
    else:
        cart_item.quantity = min(quantity, 20)
        cart_item.save()
    return redirect("cart")


@login_required
def remove_from_cart(request, cart_item_id):
    cart_item = get_object_or_404(CartItem, pk=cart_item_id, cart__user=request.user)
    cart_item.delete()
    return redirect("cart")


@login_required
def clear_cart(request):
    cart = Cart.get_for_user(request.user)
    cart.cartitem_set.all().delete()
    return redirect("cart")

@login_required
def checkout(request):
    cart = Cart.get_for_user(request.user)
    form_data = {
        "name": request.user.get_full_name() or request.user.username,
        "phone": "",
        "email": request.user.email,
        "notes": "",
    }

    if request.method == "POST":
        form_data = {
            key: request.POST.get(key, "").strip()
            for key in ("name", "phone", "email", "notes")
        }
        if not cart.cartitem_set.exists():
            messages.error(request, "Your cart is empty. Add something from the menu first.")
            return redirect("cart")
        if not form_data["name"] or not form_data["phone"]:
            messages.error(request, "Enter your name and phone number so we can reach you about your order.")
        else:
            with transaction.atomic():
                order = Order.create_from_cart(
                    cart,
                    customer_name=form_data["name"],
                    customer_phone=form_data["phone"],
                    customer_email=form_data["email"],
                    notes=form_data["notes"],
                )
            return redirect("order_confirmation", order_id=order.pk)

    return render(request, "checkout.html", {"cart": cart, "form_data": form_data})


@login_required
def order_confirmation(request, order_id):
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    return render(request, "order_confirmation.html", {"order": order})


# ---------- Staff: receiving page for incoming orders ----------

def staff_required(view):
    """Signed-out visitors go to the login page; signed-in non-staff get a 403."""
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not request.user.is_staff:
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapped


def staff_api(view):
    """Same check for the JSON endpoints, but answers with JSON instead of redirecting."""
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not (request.user.is_authenticated and request.user.is_staff):
            return JsonResponse({"error": "Sign in with a staff account."}, status=401)
        return view(request, *args, **kwargs)
    return wrapped


@staff_required
def staff_orders(request):
    return render(request, "staff_orders.html")


@require_GET
@staff_api
def staff_orders_data(request):
    """Open orders, plus anything picked up or cancelled in the last hour."""
    cutoff = timezone.now() - timedelta(hours=1)
    orders = (
        Order.objects
        .filter(Q(status__in=Order.ACTIVE_STATUSES) | Q(updated_at__gte=cutoff))
        .prefetch_related("items")
    )
    return JsonResponse([o.to_dict() for o in orders], safe=False)


@require_POST
@staff_api
def staff_update_order_status(request, order_id):
    try:
        new_status = json.loads(request.body or "{}").get("status")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid request."}, status=400)

    with transaction.atomic():
        # Lock the row so two devices tapping the same ticket can't both change it.
        order = get_object_or_404(Order.objects.select_for_update(), pk=order_id)
        if not order.can_move_to(new_status):
            return JsonResponse(
                {"error": f"Order #{order.pk} is {order.get_status_display().lower()} and can't be changed to that."},
                status=400,
            )
        order.status = new_status
        order.save(update_fields=["status", "updated_at"])
    return JsonResponse(order.to_dict())
