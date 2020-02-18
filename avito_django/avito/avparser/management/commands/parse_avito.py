
import logging
from collections import namedtuple
import datetime
from time import sleep
from math import ceil

import requests
import bs4
from django.core.management.base import BaseCommand
# испольльзуется для того, чтобы данный модуль сделать консольной командой
from django.core.management.base import CommandError
# используется для того, чтобы в случае ошибки скрипт не останавливался и просто выводилась красная ошибка

from avparser.models import Product
from avparser.models import Task
from avparser.constans import STATUS_NEW, STATUS_READY

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('avito')

InnerBlock = namedtuple(
    'Block',
    'title,price,currency,date,url'
)


class Block(InnerBlock):

    def __str__(self):
        return f'{self.title}\t{self.price} {self.currency}\t{self.date}\t{self.url}'


class AvitoParser:

    def __init__(self):
        self.session = requests.Session()
        self.session.headers = {
            'User - Agent': 'Mozilla / 5.0(X11; Ubuntu; Linux x86_64; rv: 72.0) Gecko / 20100101 Firefox / 72.0',
            'Accept - Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
        }
        self.task = None

    def find_task(self) -> Task:
        obj = Task.objects.filter(status=STATUS_NEW).first()
        if not obj:
            raise CommandError('no task found')
        self.task = obj
        logger.info(f'Работаем над заданием: {self.task}')

    def finish_task(self):
        self.task.status = STATUS_READY
        self.task.save()
        logger.info(f'Закончили задание: {self.task}')

    @staticmethod
    def parse_date(item: str):
        params = item.strip().split(' ')
        logger.debug(params)
        if len(params) == 2:
            day, time = params
            if day == 'Сегодня':
                date = datetime.date.today()
            elif day == 'Вчера':
                date = datetime.date.today() - datetime.timedelta(days=1)
            else:
                logger.error('Не смогли разобрать день:', item)
                return

            time = datetime.datetime.strptime(time, '%H:%M').time()
            return datetime.datetime.combine(date=date, time=time)

        elif len(params) == 3:
            day, month_hru, time = params
            day = int(day)
            month_map = {
                'января': 1,
                'февраля': 2,
                'марта': 3,
                'апреля': 4,
                'мая': 5,
                'июня': 6,
                'июля': 7,
                'августа': 8,
                'сентября': 9,
                'октября': 10,
                'ноября': 11,
                'декабря': 12,
            }
            month = month_map.get(month_hru)
            if not month:
                logger.error(f"Не смогли разобрать месяц: %s", item)
                return

            try:
                today = datetime.datetime.today()
                time = datetime.datetime.strptime(time, "%H:%M")
                return datetime.datetime(day=day, month=month, year=today.year, hour=time.hour, minute=time.minute)
            except ValueError:
                year = datetime.datetime.strptime(time, "%Y")
                return datetime.datetime(day=day, month=month, year=year.year, hour=0, minute=0)
            except:
                logger.error("parse date have unknown format")

        else:
            logger.error(f"Не смогли разобрать формат: ", item)
            return

    def get_pagination_limit(self):
        text = self.get_page()
        soup = bs4.BeautifulSoup(text, 'lxml')

        block = soup.select_one('span.page-title-count-1oJOc')
        limit = int(block.get_text()) / 51
        limit = ceil(limit)

        logger.debug(f"Число страниц будет: {limit}")

        return limit

    def get_page(self, page: int = None):
        params = {
            'radius': 0,
            'user': 1
        }  # это параметры get запроса
        if page and page > 1:
            params['p'] = page

        url = self.task.url

        r = self.session.get(url, params=params)
        return r.text

    def parse_block(self, item: bs4.element.Tag):
        # Выбрать блок с ссылкой и названием
        url_block = item.select_one('a.snippet-link')
        if not url_block:
            raise CommandError('bad "url_block" css')

        href = url_block.get('href')
        if href:
            url = 'https://www.avito.ru' + href
        else:
            url = None
        title = url_block.string.strip()
        if not title:
            raise CommandError(f'no title for item: {url_block}')

        # Выбрать блок с ценой
        price_block = item.select_one('span.price')
        if not price_block:
            raise CommandError('bad "price_block" css')

        price_block = price_block.get_text('\n')
        price_block = list(filter(None, map(lambda i: i.strip(), price_block.split('\n'))))
        if len(price_block) == 2:
            price, currency = price_block
            price = int(price.replace(" ", ""))
        else:
            price, currency = None, None
            logger.error(f"Что-то пошло не так при поиске цены: %s, %s", price_block, url)

        # Выбрать блок с датой размещения объявления
        date = None
        date_block = item.select_one('div.item-date div.js-item-date.c-2')
        if not date_block:
            raise CommandError('bad "date_block" css')

        absolute_date = date_block.get('data-absolute-date')
        if absolute_date:
            date = self.parse_date(item=absolute_date)

        block = Block(
            url=url,
            title=title,
            price=price,
            currency=currency,
            date=date,
        )
        logger.info(block)

        # обновляем значение, если объект в базе уже существует
        try:
            p = Product.objects.get(url=url)
            p.task = self.task
            p.title = title
            p.price = price
            p.currency = currency
            p.public_date = date
            p.save()
        except Product.DoesNotExist:
            p = Product(
                url=url,
                task=self.task,
                title=title,
                price=price,
                currency=currency,
                public_date=date,
            ).save()
            logger.info(f"Except in product url: {url}")

        return block

    def get_blocks(self, page: int = None):
        text = self.get_page(page=page)
        soup = bs4.BeautifulSoup(text, 'lxml')

        # Запрос Css селектора, состоящего из множества классов, производится через select
        container = soup.select(
            'div.snippet-horizontal.item.item_table.clearfix.js-catalog-item-enum.item-with-contact.js-item-extended')
        # logger.debug(container[0].get_text())
        for item in container:
            block = self.parse_block(item=item)
            logger.debug(block)

    def parse_all(self):
        # Выбрать какое-нибудь задание
        self.find_task()

        limit = self.get_pagination_limit()
        logger.info(f'Всего страниц: {limit}')

        for i in range(1, limit + 1):
            logger.info(f'Работаем над страницей {i}')
            self.get_blocks(page=limit)
            sleep(1)

        # Завершаем задание
        self.finish_task()


# делаем так, чтобы некий скрипт смог стать мэнеджмент командой
class Command(BaseCommand):
    help = 'Парсинг Avito'

    def handle(self, *args, **options):
        p = AvitoParser()
        p.parse_all()


def main():
    p = AvitoParser()
    p.parse_all()
    # p.get_pagination_limit()


if __name__ == "__main__":
    main()
