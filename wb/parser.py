import logging
import collections
import csv

import requests
import bs4


ParseResult = collections.namedtuple(
    'ParseResult',
    {
        'brand_name',
        'goods__name',
        'url'
    }
)

HEADERS = {
    'Бренд',
    'Товар',
    'Ссылка',
}


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('wb')


class Client:

    def __init__(self):
        self.session = requests.Session()
        self.session.headers = {
            'User - Agent': 'Mozilla / 5.0(X11; Ubuntu; Linux x86_64; rv: 72.0) Gecko / 20100101 Firefox / 72.0',
            'Accept - Language': 'ru - RU, ru',
        }
        self.result = []

    def load_page(self, page: int = None):
        url = 'https://www.wildberries.ru/catalog/muzhchinam/odezhda/vodolazki'
        res = self.session.get(url=url)  # отправка запроса по url
        res.raise_for_status()  # проверяем статус страницы
        return res.text

    def parse_page(self, text: str):
        soup = bs4.BeautifulSoup(text, 'lxml')
        container = soup.select('div.dtList.i-dtList.j-card-item')
        for block in container:
            self.parse_block(block=block)

    def parse_block(self, block: bs4.element.Tag):
        url_block = block.select_one('a.ref_goods_n_p')
        if not url_block:
            logger.error('no url_block')
            return

        url = url_block.get('href')
        if not url:
            logger.error('no href')
            return

        name_block = block.select_one('div.dtlist-inner-brand-name')
        if not name_block:
            logger.error(f'no name_block on {url}')
            return

        brand_name = name_block.select_one('strong.brand-name')
        if not name_block:
            logger.error(f'no brand_name on {url}')
            return

        # Wrangler /
        brand_name = brand_name.text
        brand_name = brand_name.replace("/", "").strip()

        goods_name = name_block.select_one('span.goods-name')
        if not goods_name:
            logger.error(f'no goods_name on {url}')
            return

        goods_name = goods_name.text.strip()

        self.result.append(ParseResult(
            url=url,
            brand_name=brand_name,
            goods__name=goods_name,
        ))

        logger.debug('%s, %s, %s', url, brand_name, goods_name)
        logger.debug('-' * 100)

    def save_results(self):
        path = '/home/alexander/Документы/python/parsers/wb/test.csv'
        with open(path, 'w') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
            writer.writerow(HEADERS)
            for item in self.result:
                writer.writerow(item)  # так можно делать, так как item - tuple

    def run(self):
        text = self.load_page()
        self.parse_page(text=text)
        logger.info(f'Получили {len(self.result)} карточек')

        self.save_results()


if __name__ == '__main__':
    parser = Client()
    parser.run()