import time
import traceback
from . import Tweet


class UserTweets(dict):
    def __init__(self, user_id, http, get_replies: bool = True, wait_time=2, throttle_on_fail=10, cursor=None):
        super().__init__()
        self.tweets = []
        self.get_replies = get_replies
        self.cursor = cursor
        self.is_next_page = True
        self.http = http
        self.user_id = user_id
        self.wait_time = wait_time
        self.throttle_on_fail = throttle_on_fail
        # self._get_tweets(user_id, pages, get_replies, wait_time)

    @staticmethod
    def _get_entries(response):
        timeline = response.json()['data']['user']['result']['timeline_v2']
        if 'timeline' in timeline:
            instructions = timeline['timeline']['instructions']
            for instruction in instructions:
                if instruction.get("type") == "TimelineAddEntries":
                    return instruction['entries']

        return []

    @staticmethod
    def _get_tweet_content_key(tweet):
        if str(tweet['entryId']).split("-")[0] == "tweet":
            if 'result' in tweet['content']['itemContent']['tweet_results']:
                return [tweet['content']['itemContent']['tweet_results']['result']]
            else:
                return []

        if str(tweet['entryId']).split("-")[0] == "homeConversation":
            return [item['item']['itemContent']['tweet_results']['result']['tweet'] for item in tweet["content"]["items"]]

        return []

    def get_next_page(self, user_id, get_replies):
        _tweets = []
        if self.is_next_page:
            response = self.http.get_tweets(user_id, replies=get_replies, cursor=self.cursor)

            try:
                entries = self._get_entries(response)
            except Exception as e:
                time.sleep(self.throttle_on_fail)
                response = self.http.get_tweets(user_id, replies=get_replies, cursor=self.cursor)
                try:
                    entries = self._get_entries(response)
                except:
                    raise Exception(f"Error getting page entries for user {user_id} after throttle: {e}. Response: {response}")

            for entry in entries:
                tweets = self._get_tweet_content_key(entry)
                for tweet in tweets:
                    # Skip deleted/suspended tweets
                    if tweet['__typename'] == 'TweetTombstone':
                        continue

                    try:
                        _tweets.append(Tweet(response, tweet, self.http))
                    except:
                        traceback.print_exc()
                        pass

            self.is_next_page = self._get_cursor(entries)

            self['is_next_page'] = self.is_next_page
            self['cursor'] = self.cursor

            return _tweets

    def get_tweets_page_iterator(self, pages):
        for page in range(1, int(pages) + 1):
            tweets = self.get_next_page(self.user_id, self.get_replies)
            yield tweets
            
            if self.is_next_page and page != pages:
                time.sleep(self.wait_time)

    def get_tweets(self, pages):
        all_tweets = []
        for page in range(1, int(pages) + 1):
            tweets = self.get_next_page(self.user_id, self.get_replies)
            all_tweets += tweets

            if self.is_next_page and page != pages:
                time.sleep(self.wait_time)
        return all_tweets

    def _get_cursor(self, entries):
        for entry in entries:
            if str(entry['entryId']).split("-")[0] == "cursor":
                if entry['content']['cursorType'] == "Bottom":
                    newCursor = entry['content']['value']

                    if newCursor == self.cursor:
                        return False

                    self.cursor = newCursor
                    return True

        return False

    def __getitem__(self, index):
        return self.tweets[index]

    def __iter__(self):
        for __tweet in self.tweets:
            yield __tweet

    def __len__(self):
        return len(self.tweets)

    def __repr__(self):
        return f"UserTweets(user_id={self.user_id}, count={self.__len__()})"


