from tweety.bot import Tweety

NUM_PAGES = 2

def test_get_user_tweets():
    tweety = Tweety()
    tweets_iterator = tweety.paginate_tweets('44196397', pages=NUM_PAGES)

    num_pages = 0
    for tweets in tweets_iterator:
        assert len(tweets) >= 38 # Supposed to be 40 as provided in the builder ?
        assert tweets[0].author.rest_id == '44196397'
        num_pages += 1

    assert num_pages == NUM_PAGES