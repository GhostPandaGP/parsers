from django.contrib import admin
import logging

from .forms import ProductForm, TaskForm
from .models import Product, Task

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('admin')

PRICE_FILTER_STEPS = 10


class PriceFilter(admin.SimpleListFilter):
    title = 'Цена'
    parameter_name = 'price'

    # то, что отображается сбоку админки
    def lookups(self, request, model_admin):
        # Вытащить полный список цен
        prices = [c.price for c in model_admin.model.objects.all()]
        prices = filter(None, prices)

        # TODO: найти "кластера цен", т.е. интервалы, внутри которых точно есть значения

        # Побить его на PRICE_FILTER_STEPS интервалов
        max_price = max(prices)
        chunk = int(max_price / PRICE_FILTER_STEPS)
        logger.info(f'max_price = {max_price}, chunk = {chunk}')

        intervals = [
            (f'{chunk * i}, {chunk * (i + 1)}', f'{chunk * i} - {chunk * (i + 1)}')
            for i in range(PRICE_FILTER_STEPS)
        ]
        return intervals

    # когда приходит выбранный элемент, то эта функция его обрабатывает
    def queryset(self, request, queryset):
        choice = self.value() or ''
        if not choice:
            return queryset
        choice = choice.split(',')
        if not len(choice) == 2:
            return queryset
        price_form, price_to = choice

        # distinct - ставим, чтобы получить уникальные значения
        return queryset.distinct().filter(price__gte=price_form, price__lt=price_to)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('pk', 'task', 'title', 'price', 'public_date', 'url')
    list_filter = (
        'currency',
        'public_date',
        'task',
        PriceFilter
    )
    form = ProductForm


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('pk', 'title', 'url', 'status')
    list_filter = ('status',)
    form = TaskForm
