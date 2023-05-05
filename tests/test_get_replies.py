from tweety.bot import Tweety
from tweety.types import Tweet

NUM_PAGES = 2

def test_get_replies():
    tweety = Tweety()
    tweets = tweety.get_replies('1587156152609021958')

    assert type(tweets[0]) == Tweet
    assert tweets[0].text == '@sukutodo 😍'
    assert tweets[0].reply_to.id == '1587156152609021958'

