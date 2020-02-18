from collections import namedtuple


InnerBlock = namedtuple(
    'Block',
    'title,price,currency,date,url'
)


class Block(InnerBlock):

    def __str__(self):
        return f'{self.title}\t{self.price} {self.currency}\t{self.date}\t{self.url}'


x = Block(title='x', price='x', currency=111, date=111, url='x')
print(x)