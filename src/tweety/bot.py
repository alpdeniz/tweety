import functools
from .exceptions_ import *
from .http import Request
from .types.usertweet import UserTweets
from .types.search import Search
from .types.twDataTypes import User, Trends, Tweet


def valid_profile(f):
    @functools.wraps(f)
    def wrapper(self, *args, **kwargs):
        if self.profile_url is None:
            raise ValueError("No Username Provided , Please initiate the class using a username or profile URL")

        if self.user.protected:
            username = self.profile_url.split("/")[-1]
            raise UserProtected(f"User {username} is Protected")

        try:
            return f(self, *args, **kwargs)
        except (UserProtected, UserNotFound) as e:
            raise e
        except Exception as e:
            raise UnknownError(e)

    return wrapper


class Tweety:
    def __init__(self, max_retries: int = 10, proxy: dict = None):
        """
        Initialize the Twitter Class

        :param max_retries: (`int`) Number of retries the script would make , if the guest token wasn't found
        :param proxy: (`dict`) Provide the proxy you want to use while making a request
        """

        self.max_retries = max_retries
        if proxy and proxy is not None:
            if proxy.get("http") and proxy.get("https"):
                self.proxy = dict(http=proxy['http'], https=proxy['https'])
            else:
                raise ProxyParseError()
        else:
            self.proxy = None

        self.request = Request(max_retries=self.max_retries, proxy=self.proxy)

    def get_user(self, screen_name: str):
        """
        Set user

        :param screen_name: (`str`) Profile URL or The Username of the user you are dealing with
        """

        user = self.request.get_user_by_sceen_name(screen_name)
        if user:
            return User(user)
        raise UserNotFound("User {} not Found".format(screen_name))

    @property
    def user_id(self):
        """
        Get the user unique twitter id

        :return: int
        """

        return self.user.rest_id

    def paginate_tweets(self, user_id: str, pages: int = 1, replies: bool = False, wait_time: int = 2, cursor: str = None):
        """
        Get the tweets from a user

        :param pages: (`int`) number of pages to be scraped
        :param replies: (`boolean`) get the replied tweets of the user too
        :param wait_time: (`int`) seconds to wait between multiple requests
        :param cursor: Pagination cursor if you want to get the pages from that cursor up-to (This cursor is different from actual API cursor)


        :return: .types.usertweet.UserTweets
        """

        userTweets = UserTweets(user_id, self.request, replies, wait_time, cursor)
        return userTweets.get_tweets_page_iterator(pages)

    def get_tweets(self, pages: int = 1, replies: bool = False, wait_time: int = 2, cursor: str = None):
        """
        Get the tweets from a user

        :param pages: (`int`) number of pages to be scraped
        :param replies: (`boolean`) get the replied tweets of the user too
        :param wait_time: (`int`) seconds to wait between multiple requests
        :param cursor: Pagination cursor if you want to get the pages from that cursor up-to (This cursor is different from actual API cursor)


        :return: .types.usertweet.UserTweets
        """
        if wait_time is None:
            wait_time = 0

        return UserTweets(self.user_id, self.request, replies, wait_time, cursor).get_tweets(pages)

    def get_trends(self):
        """
        Get the Trends from you locale

        :return:list of .types.twDataTypes.Trends
        """
        trends = []
        response = self.request.get_trends()
        for i in response.json()['timeline']['instructions'][1]['addEntries']['entries'][1]['content']['timelineModule']['items']:
            data = {
                "name": i['item']['content']['trend']['name'],
                "url": str(i['item']['content']['trend']['url']['url']).replace("twitter://",
                                                                                "https://twitter.com/").replace("query",
                                                                                                                "q"),
            }
            try:
                if i['item']['content']['trend']['trendMetadata']['metaDescription']:
                    data['tweet_count'] = i['item']['content']['trend']['trendMetadata']['metaDescription']
            except:
                pass
            trends.append(Trends(data))
        return trends

    def search(self, keyword: str, pages: int = 1, filter_: str = None, wait_time: int = 2, cursor: str = None):
        """
        Search for a keyword or hashtag on Twitter

        :param keyword: (`str`) The keyword which is supposed to be searched
        :param pages: (`int`) The number of pages to get
        :param filter_: (
           `str`| `filters.SearchFilters.Users()`| `filters.SearchFilters.Latest()` | `filters.SearchFilters.Photos()` | `filters.SearchFilters.Videos()`
        )
        :param wait_time : (`int`) seconds to wait between multiple requests
        :param cursor: (`str`) Pagination cursor if you want to get the pages from that cursor up-to (This cursor is different from actual API cursor)


        :return: .types.search.Search
        """
        if wait_time is None:
            wait_time = 0

        return Search(keyword, self.request, pages, filter_, wait_time, cursor)

    def tweet_detail(self, identifier: str):
        """
        Get Detail of a single tweet

        :param identifier: (`str`) The unique identifier of the tweet , either the `Tweet id` or `Tweet Link`

        :return: .types.twDataTypes.Tweet
        """

        if str(identifier).startswith("https://"):
            if str(identifier).endswith("/"):
                tweetId = str(identifier)[:-1].split("/")[-1]
            else:
                tweetId = str(identifier).split("/")[-1]
        else:
            tweetId = identifier

        r = self.request.get_tweet_detail(tweetId)

        try:
            for entry in r.json()['data']['threaded_conversation_with_injections_v2']['instructions'][0]['entries']:
                if str(entry['entryId']).split("-")[0] == "tweet":
                    raw_tweet = entry['content']['itemContent']['tweet_results']['result']
                    # skip deleted or protected tweets
                    # raw_tweet[__typename'] = 'TweetTombstone'
                    if 'rest_id' in raw_tweet:
                        if raw_tweet['rest_id'] == str(identifier):
                            return Tweet(r, raw_tweet, self.request, True, False, True)

            raise InvalidTweetIdentifier()
        except KeyError:
            raise InvalidTweetKey()

    def get_replies(self, tweetId: str):
        """
        Get replies of a tweet

        :param tweetId: (`str`) The unique identifier of the tweet

        :return: [.types.twDataTypes.Tweet]
        """

        r = self.request.get_tweet_detail(tweetId)

        tweets = []
        reply_to_tweet = None
        try:
            for entry in r.json()['data']['threaded_conversation_with_injections_v2']['instructions'][0]['entries']:
                # entryId is in form "tweet/conversationthread-{tweet_id/conv_id}[-(tweet/cursor-showmore)-{tweet_id/cursor?_id}]"
                info = str(entry['entryId']).split("-")
                if info[0] == "tweet":
                    raw_tweet = entry['content']['itemContent']['tweet_results']['result']
                    reply_to_tweet = Tweet(r, raw_tweet, self.request, True, False, True)
                if info[0] == "conversationthread":
                    replies = entry['content']['items']
                    for reply in replies:
                        info = str(reply['entryId']).split("-")
                        if "cursor" not in info:
                            raw_tweet = reply['item']['itemContent']['tweet_results']['result']
                            reply_tweet = Tweet(r, raw_tweet, self.request, True, False, True)
                            setattr(reply_tweet, 'reply_to', reply_to_tweet)
                            setattr(reply_tweet, 'is_reply', True)
                            tweets.append(reply_tweet)

            return tweets
        except KeyError:
            raise InvalidTweetIdentifier()
