from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("menu/", views.menu, name="menu"),
    path("item/<int:pk>/", views.menu_item_detail, name="menu_item"),
    path("add-to-cart/<int:item_id>/", views.add_to_cart, name="add_to_cart"),
    path("login/", views.CustomLoginView.as_view(), name="login"),
    path("register/", views.register, name="register"),
    path("logout/", LogoutView.as_view(next_page="index"), name="logout"),
    path("cart/", views.cart, name="cart"),
    path("checkout/", views.checkout, name="checkout"),
    path("cart/update/<int:cart_item_id>/", views.update_cart_item, name="update_cart_item"),
    path("cart/remove/<int:cart_item_id>/", views.remove_from_cart, name="remove_from_cart"),
    path("cart/clear/", views.clear_cart, name="clear_cart"),
    path("orders/<int:order_id>/", views.order_confirmation, name="order_confirmation"),
    path("staff/orders/", views.staff_orders, name="staff_orders"),
    path("staff/orders/data/", views.staff_orders_data, name="staff_orders_data"),
    path("staff/orders/<int:order_id>/status/", views.staff_update_order_status, name="staff_update_order_status"),
]
