from dateutil import parser
import dateutil

WORKBOOK_HEADERS = ['Created on', 'author', 'is_retweet', 'is_reply', 'tweet_id', 'tweet_body', 'language', 'likes',
                    'retweet_count', 'source', 'medias', 'user_mentioned', 'urls', 'hashtags', 'symbols']


class Tweet(dict):
    def __init__(self, raw_response, raw_tweet, http, get_threads=False, is_legacy_user=False, get_reply=False):  # noqa
        super().__init__()
        self.http = http
        self.__raw_response = raw_response
        self.__raw_tweet = raw_tweet
        self.__is_legacy_user = is_legacy_user
        self.__replied_to = None
        self._get_reply = get_reply
        self.__formatted_tweet = self._format_tweet()
        self.id = None

        if get_threads:
            self._get_threads()

        for key, value in self.__formatted_tweet.items():
            setattr(self, key, value)
            self[key] = value

    def __repr__(self):
        return f"Tweet(id={self.id}, author={self.author}, created_on={self.created_on}, threads={len(self.threads) if self.threads else None})"  # noqa

    def __iter__(self):
        if self.threads:  # noqa
            for thread_ in self.threads:  # noqa
                yield thread_


    def _format_tweet(self):
        original_tweet = self._get_original_tweet()
        self.id = tweet_rest_id = self._get_id()
        tweet_author = self.__raw_tweet['core']

        created_on = dateutil.parser.parse(original_tweet.get("created_at"))
        author = UserLegacy(tweet_author) if self.__is_legacy_user else User(tweet_author, 3)
        is_retweet = self._is_retweet(original_tweet)
        retweeted_tweet = self._get_retweeted_tweet(is_retweet,original_tweet)
        text = self._get_tweet_text(original_tweet, is_retweet)
        is_quoted = self._is_quoted(original_tweet)
        quoted_tweet = self._get_quoted_tweet(is_quoted)
        is_reply = self._is_reply(original_tweet)
        is_sensitive = self._is_sensitive(original_tweet)
        reply_counts = self._get_reply_counts(original_tweet)
        quote_counts = self._get_quote_counts(original_tweet)
        replied_to = self.__replied_to = self._get_reply_to(is_reply, original_tweet, )
        vibe = self._get_vibe()
        views = self._get_views()

        return {
            "created_on": created_on,
            "author": author,
            "is_quoted": is_quoted,
            "quoted_tweet": quoted_tweet,
            "quote_counts": quote_counts,
            "is_retweet": is_retweet,
            "retweeted_tweet": retweeted_tweet,
            "is_reply": is_reply,
            "vibe": vibe,
            "reply_counts": reply_counts,
            "is_possibly_sensitive": is_sensitive,
            "id": tweet_rest_id,
            "tweet_body": text,
            "text": text,
            "language": self._get_language(original_tweet),
            "likes": self._get_likes(original_tweet),
            "card": self._get_card(),
            "place": self._get_place(original_tweet),
            "retweet_counts": self._get_retweet_counts(original_tweet),
            "source": self._get_source(self.__raw_tweet),
            "media": self._get_tweet_media(original_tweet),
            "user_mentions": self._get_tweet_mentions(original_tweet),
            "urls": self._get_tweet_urls(original_tweet),
            "hashtags": self._get_tweet_hashtags(original_tweet),
            "symbols": self._get_tweet_symbols(original_tweet),
            "views": views,
            "reply_to": replied_to,
            "threads": [],
            "comments": []
        }

    def _get_id(self):
        if self.__raw_tweet.get("rest_id"):
            return self.__raw_tweet['rest_id']

        if self.__raw_tweet.get("tweet"):
            return self.__raw_tweet['tweet']['rest_id']

    def _get_original_tweet(self):
        if self.__raw_tweet.get("tweet"):
            self.__raw_tweet = self.__raw_tweet['tweet']

        if self.__raw_tweet.get("legacy"):
            return self.__raw_tweet['legacy']

        return self.__raw_tweet

    def _get_retweeted_tweet(self, is_retweet, original_tweet):
        if is_retweet:
            try:
                retweet = original_tweet['retweeted_status_result']['result']
                return Tweet(None, retweet, self.http)
            except Exception as e:
                print(f"Error getting retweet: {e}, original tweet: {original_tweet}")

        return None

    def _get_threads(self):
        if not self.__raw_response:
            self.__raw_response = self.http.get_tweet_detail(self.id)  # noqa

        for entry in self.__raw_response.json()['data']['threaded_conversation_with_injections_v2']['instructions'][0]['entries']:
            if str(entry['entryId']).split("-")[0] == "conversationthread":
                for item in entry['content']['items']:
                    try:
                        tweetType = item["item"]["itemContent"]["tweetDisplayType"]
                        tweet = item['item']['itemContent']['tweet_results']['result']

                        if not self.__replied_to or self.__replied_to.id != tweet['rest_id']:
                            self.__formatted_tweet['threads' if tweetType == "SelfThread" else 'comments'].append(
                                Tweet(None, tweet, self.http))
                    except KeyError as e:
                        pass

    def _get_quoted_tweet(self, is_quoted):
        if is_quoted:
            raw_response = self.__raw_response
            raw_tweet = None
            try:
                if self.__raw_tweet.get("quoted_status_result"):
                    raw_tweet = self.__raw_tweet['quoted_status_result']['result']
                # if not raw_tweet and self.__raw_tweet.get("legacy"):
                #     raw_tweet = self.__raw_tweet['legacy']['retweeted_status_result']['result']['quoted_status_result']['result']
                return Tweet(raw_response, raw_tweet, self.http)
            except:
                return None

        return None

    def _get_card(self):
        if self.__raw_tweet.get("card"):
            try:
                return Card(self.__raw_tweet['card'])
            except KeyError:
                pass
        return None

    def _get_vibe(self):
        if self.__raw_tweet.get("vibe"):
            vibeImage = self.__raw_tweet['vibe']['imgDescription']
            vibeText = self.__raw_tweet['vibe']['text']
            return f"{vibeImage} {vibeText}"

        return ""

    def _get_views(self):
        if self.__raw_tweet.get("views"):
            return self.__raw_tweet['views'].get('count', 'Unavailable')

        return 0

    def _get_reply_to(self, is_reply, tweet):
        if is_reply and self._get_reply:
            tweet_id = tweet['in_reply_to_status_id_str']
            response = self.http.get_tweet_detail(tweet_id)
            for entry in response.json()['data']['threaded_conversation_with_injections_v2']['instructions'][0]['entries']:
                if str(entry['entryId']).split("-")[0] == "tweet":
                    raw_tweet = entry['content']['itemContent']['tweet_results']['result']
                    return Tweet(response, raw_tweet, self.http)

        elif is_reply and not self._get_reply:
            return tweet['in_reply_to_screen_name']
        return None

    @staticmethod
    def _is_sensitive(original_tweet):
        return original_tweet.get("possibly_sensitive", False)

    @staticmethod
    def _get_reply_counts(original_tweet):
        return original_tweet.get("reply_count", 0)

    @staticmethod
    def _get_quote_counts(original_tweet):
        return original_tweet.get("quote_count", 0)

    @staticmethod
    def _is_retweet(original_tweet):
        if original_tweet.get("retweeted"):
            return True

        if str(original_tweet.get('full_text', "")).startswith("RT"):
            return True

        return False

    @staticmethod
    def _is_reply(original_tweet):
        tweet_keys = list(original_tweet.keys())
        required_keys = ["in_reply_to_status_id_str", "in_reply_to_user_id_str", "in_reply_to_screen_name"]
        return any(x in tweet_keys and original_tweet[x] is True for x in required_keys)

    @staticmethod
    def _is_quoted(original_tweet):
        if original_tweet.get("is_quote_status"):
            return True

        return False

    @staticmethod
    def _get_language(original_tweet):
        return original_tweet.get('lang', "")

    @staticmethod
    def _get_likes(original_tweet):
        return original_tweet.get("favorite_count", 0)

    @staticmethod
    def _get_place(original_tweet):
        if original_tweet.get('place'):
            return Place(original_tweet['place'])

        return None

    @staticmethod
    def _get_retweet_counts(original_tweet):
        return original_tweet.get('retweet_count', 0)

    @staticmethod
    def _get_source(original_tweet):
        if original_tweet.get('source'):
            return str(original_tweet['source']).split(">")[1].split("<")[0]

        return ""

    @staticmethod
    def _get_tweet_text(original_tweet, is_retweet):
        if is_retweet:
            try:
                if 'legacy' in original_tweet['retweeted_status_result']['result']:
                    return original_tweet['retweeted_status_result']['result']['legacy']['full_text']
                else:
                    return original_tweet['retweeted_status_result']['result']['tweet']['legacy']['full_text']
            except Exception as e:
                print(f"Error getting retweeted tweet text: {e}, retweeted status result: {original_tweet}")

        if original_tweet.get('full_text'):
            return original_tweet['full_text']

        return ""

    @staticmethod
    def _get_tweet_media(original_tweet):
        if not original_tweet.get("extended_entities"):
            return []

        if not original_tweet['extended_entities'].get("media"):
            return []

        return [Media(media) for media in original_tweet['extended_entities']['media']]

    @staticmethod
    def _get_tweet_mentions(original_tweet):
        if not original_tweet.get("entities"):
            return []

        if not original_tweet['entities'].get("user_mentions"):
            return []

        return [ShortUser(user) for user in original_tweet['entities']['user_mentions']]

    @staticmethod
    def _get_tweet_urls(original_tweet):
        if not original_tweet.get("entities"):
            return []

        if not original_tweet['entities'].get("urls"):
            return []

        return [url for url in original_tweet['entities']['urls']]

    @staticmethod
    def _get_tweet_hashtags(original_tweet):
        if not original_tweet.get("entities"):
            return []

        if not original_tweet['entities'].get("hashtags"):
            return []

        return [hashtag for hashtag in original_tweet['entities']['hashtags']]

    @staticmethod
    def _get_tweet_symbols(original_tweet):
        if not original_tweet.get("entities"):
            return []

        if not original_tweet['entities'].get("symbols"):
            return []

        return [symbol for symbol in original_tweet['entities']['symbols']]


class Media(dict):
    def __init__(self, media_dict):
        super().__init__()
        self.__dictionary = media_dict
        self.display_url = self.__dictionary.get("display_url")
        self.expanded_url = self.__dictionary.get("expanded_url")
        self.id = self.__dictionary.get("id_str")
        self.indices = self.__dictionary.get("indices")
        self.media_url_https = self.__dictionary.get("media_url_https")
        self.type = self.__dictionary.get("type")
        self.url = self.__dictionary.get("url")
        self.features = self.__dictionary.get("features")
        self.media_key = self.__dictionary.get("media_key")
        self.mediaStats = self.__dictionary.get("mediaStats")
        self.sizes = self.__dictionary.get("sizes")
        self.original_info = self.__dictionary.get("original_info")
        self.file_format = self.media_url_https.split(".")[-1] if self.type == "photo" else None
        self.streams = []
        if self.type == "video" or self.type == "animated_gif":
            self.__parse_video_streams()

        for k, v in vars(self).items():
            if not k.startswith("_"):
                self[k] = v

    def __parse_video_streams(self):
        videoDict = self.__dictionary.get("video_info")
        if videoDict:
            for i in videoDict.get("variants"):
                if not i.get("content_type").split("/")[-1] == "x-mpegURL":
                    self.streams.append(
                        Stream(i, videoDict.get("duration_millis", 0), videoDict.get("aspect_ratio"))
                    )

    def __repr__(self):
        return f"Media(id={self.id}, type={self.type})"


class Stream(dict):
    def __init__(self, videoDict, length, ratio):
        super().__init__()
        self.__dictionary = videoDict
        self.bitrate = self.__dictionary.get("bitrate")
        self.content_type = self.__dictionary.get("content_type")
        self.url = self.__dictionary.get("url")
        self.length = length
        self.aspect_ratio = ratio
        try:
            self.res = int(self.url.split("/")[7].split("x")[0]) * int(self.url.split("/")[7].split("x")[1])
        except (ValueError, IndexError):
            try:
                self.res = int(self.url.split("/")[6].split("x")[0]) * int(self.url.split("/")[6].split("x")[1])
            except (ValueError, IndexError):
                self.res = None

        for k, v in vars(self).items():
            if not k.startswith("_"):
                self[k] = v

    def __repr__(self):
        return f"Stream(content_type={self.content_type}, length={self.length}, bitrate={self.bitrate}, res={self.res})"


class ShortUser(dict):
    def __init__(self, user_dict):
        super().__init__()
        self.__dictionary = user_dict
        self.id = self.__dictionary.get("id_str")
        self.name = self.__dictionary.get("name")
        self.screen_name = self.username = self.__dictionary.get("screen_name")

        for k, v in vars(self).items():
            if not k.startswith("_"):
                self[k] = v

    def __repr__(self):
        return f"ShortUser(id={self.id}, name={self.name})"



class User(dict):
    def __init__(self, user_dict, type_=1):
        super().__init__()
        if type_ == 1:
            self.__dictionary = user_dict['data']['user']['result']
        elif type_ == 2:
            self.__dictionary = user_dict
        else:
            self.__dictionary = user_dict['user_results']['result']

        self.id = self.__dictionary.get("id")
        self.rest_id = self._get_rest_id(self.__dictionary)
        self.created_at = self._get_created_at(self.__dictionary)
        self.default_profile = self._get_key(self.__dictionary, "default_profile")
        self.default_profile_image = self._get_key(self.__dictionary, "default_profile_image")
        self.description = self._get_key(self.__dictionary, "description")
        self.entities = self._get_key(self.__dictionary, "entities")
        self.fast_followers_count = self._get_key(self.__dictionary, "fast_followers_count")
        self.favourites_count = self._get_key(self.__dictionary, "favourites_count")
        self.followers_count = self._get_key(self.__dictionary, "followers_count")
        self.friends_count = self._get_key(self.__dictionary, "friends_count")
        self.has_custom_timelines = self._get_key(self.__dictionary, "has_custom_timelines")
        self.is_translator = self._get_key(self.__dictionary, "is_translator")
        self.listed_count = self._get_key(self.__dictionary, "listed_count")
        self.location = self._get_key(self.__dictionary, "location")
        self.media_count = self._get_key(self.__dictionary, "media_count")
        self.name = self._get_key(self.__dictionary, "name")
        self.normal_followers_count = self._get_key(self.__dictionary, "normal_followers_count")
        self.profile_banner_url = self._get_key(self.__dictionary, "profile_banner_url")
        self.profile_image_url_https = self._get_key(self.__dictionary, "profile_image_url_https")
        self.profile_interstitial_type = self._get_key(self.__dictionary, "profile_interstitial_type")
        self.protected = self._get_key(self.__dictionary, "protected")
        self.screen_name = self.username = self._get_key(self.__dictionary, "screen_name")
        self.statuses_count = self._get_key(self.__dictionary, "statuses_count")
        self.translator_type = self._get_key(self.__dictionary, "translator_type")
        self.verified = self._get_key(self.__dictionary, "verified")
        # self.verified_type = self._get_key(self.__dictionary, "verified_type")
        self.possibly_sensitive = self._get_key(self.__dictionary, "possibly_sensitive")
        self.pinned_tweets = self._get_key(self.__dictionary, "pinned_tweet_ids_str")

        self.profile_url = "https://twitter.com/{}".format(self.screen_name)

        for k, v in vars(self).items():
            if not k.startswith("_"):
                self[k] = v

    def __repr__(self):
        return f"User(id={self.rest_id}, name={self.name}, username={self.screen_name}, followers={self.followers_count}, verified={self.verified})"


    @staticmethod
    def _get_rest_id(user):
        if user.get("rest_id"):
            return user['rest_id']

        if user.get("id_str"):
            return user['id_str']

        return None

    @staticmethod
    def _get_created_at(user):
        date = None
        if user.get("legacy"):
            date = user['legacy']['created_at']

        if not date and user.get("created_at"):
            date = user["created_at"]

        return parser.parse(date) if date else None

    @staticmethod
    def _get_key(user, key):
        keyValue = None
        if user.get("legacy"):
            keyValue = user['legacy'].get(key)

        if not keyValue and user.get(key):
            keyValue = user[key]

        return keyValue


class Trends:
    def __init__(self, trends_dict):
        self.__dictionary = trends_dict
        self.name = self.__dictionary.get("name")
        self.url = self.__dictionary.get("url")
        self.tweet_count = self.__dictionary.get("tweet_count")

    def __repr__(self):
        return f"Trends(name={self.name})"

    def to_dict(self):
        return self.__dictionary


class UserLegacy(dict):
    def __init__(self, user_dict):
        super().__init__()
        self.__dictionary = user_dict
        self.id = self.__dictionary.get("id")
        self.rest_id = self.__dictionary.get("id")
        self.created_at = parser.parse(self.__dictionary.get("created_at")) if self.__dictionary.get("created_at") else None
        self.default_profile = self.__dictionary.get("default_profile")
        self.default_profile_image = self.__dictionary.get("default_profile_image")
        self.description = self.__dictionary.get("description")
        self.entities = self.__dictionary.get("entities")
        self.fast_followers_count = self.__dictionary.get("fast_followers_count")
        self.favourites_count = self.__dictionary.get("favourites_count")
        self.followers_count = self.__dictionary.get("followers_count")
        self.friends_count = self.__dictionary.get("friends_count")
        self.has_custom_timelines = self.__dictionary.get("has_custom_timelines")
        self.is_translator = self.__dictionary.get("is_translator")
        self.listed_count = self.__dictionary.get("listed_count")
        self.location = self.__dictionary.get("location")
        self.media_count = self.__dictionary.get("media_count")
        self.name = self.__dictionary.get("name")
        self.normal_followers_count = self.__dictionary.get("normal_followers_count")
        self.profile_banner_url = self.__dictionary.get("profile_banner_url")
        self.profile_image_url_https = self.__dictionary.get("profile_image_url_https")
        self.profile_interstitial_type = self.__dictionary.get("profile_interstitial_type")
        self.protected = self.__dictionary.get("protected")
        self.screen_name = self.__dictionary.get("screen_name")
        self.statuses_count = self.__dictionary.get("statuses_count")
        self.translator_type = self.__dictionary.get("translator_type")
        self.verified = self.__dictionary.get("verified")
        # self.verified_type = self.__dictionary.get("verified_type")
        self.possibly_sensitive = self.__dictionary.get("possibly_sensitive")
        self.pinned_tweets = self.__dictionary.get("pinned_tweet_ids_str")
        self.profile_url = "https://twitter.com/{}".format(self.screen_name)

        for k, v in vars(self).items():
            if not k.startswith("_"):
                self[k] = v

    def __repr__(self):
        return f"User(id={self.rest_id}, name={self.name}, followers={self.followers_count} , verified={self.verified})"

    def to_dict(self):
        return self.__dictionary


class Card(dict):
    def __init__(self, card_dict):
        super().__init__()
        self._dict = card_dict
        self._bindings = self._dict['legacy'].get("binding_values")
        self.rest_id = self._dict.get("rest_id")
        self.name = self._dict['legacy'].get("name")
        self.choices = []
        self.end_time = None
        self.last_updated_time = None
        self.duration = None
        self.user_ref = [User(user, 2) for user in self._dict['legacy']["user_refs"]] if self._dict['legacy'].get("user_refs") else []
        self.__parse_choices()

        for k, v in vars(self).items():
            if not k.startswith("_"):
                self[k] = v

    def __parse_choices(self):
        for _ in self._bindings:
            _key = _.get("key").split("_")
            if "choice" in _key[0] and "label" in _key[1]:
                _cardName = _key[0]
                _cardValue = _['value']['string_value']
                _cardValueType = _['value']['type']
                _cardCounts = 0
                _cardCountsType = None
                for __ in self._bindings:
                    __key = __.get("key")
                    if __key[0] == _key[0] and "count" in __key[1]:
                        _cardCounts = __['value']['string_value']
                        _cardCountsType = __['value']['type']
                _r = {
                    "card_name": _cardName,
                    "card_value": _cardValue,
                    "card_value_type": _cardValueType,
                    "card_counts": _cardCounts,
                    "card_counts_type": _cardCountsType,
                }
                self.choices.append(Choice(_r))
            elif _key[0] == "end" and _key[1] == "datetime":
                self.end_time = parser.parse(_['value']['string_value'])
                # last_updated_datetime_utc
            elif _key[0] == "last" and _key[1] == "updated":
                self.last_updated_time = parser.parse(_['value']['string_value'])
                # duration_minutes
            elif _key[0] == "duration" and _key[1] == "minutes":
                self.duration = _['value']['string_value']

    def __repr__(self):
        return f"Card(id={self.rest_id}, choices={len(self.choices) if self.choices else []}, end_time={self.end_time}, duration={len(self.duration) if self.duration else 0} minutes)"


class Choice(dict):
    def __init__(self, _dict):
        super().__init__()
        self._dict = _dict
        self.name = self._dict.get("card_name")
        self.value = self._dict.get("card_value")
        self.type = self._dict.get("card_value_type")
        self.counts = self._dict.get("card_counts")
        self.counts_type = self._dict.get("card_counts_type")

        for k, v in vars(self).items():
            if not k.startswith("_"):
                self[k] = v

    def __repr__(self):
        return f"Choice(name={self.name}, value={self.value}, counts={self.counts})"


class Place(dict):
    def __init__(self, place_dict):
        super().__init__()
        self.__dict = place_dict
        self.id = self.__dict.get("id")
        self.country = self.__dict.get("country")
        self.country_code = self.__dict.get("country_code")
        self.full_name = self.__dict.get("full_name")
        self.name = self.__dict.get("name")
        self.url = self.__dict.get("url")
        self.coordinates = self.parse_coordinates()

        for k, v in vars(self).items():
            if not k.startswith("_"):
                self[k] = v

    def parse_coordinates(self):
        results = []
        for i in self.__dict['bounding_box'].get("coordinates"):
            for p in i:
                coordinates = [p[1], p[0]]
                if coordinates not in results:
                    results.append([coordinates[0], coordinates[1]])

        return [Coordinates(i[0], i[1]) for i in results]

    def __repr__(self):
        return f"Place(id={self.id}, name={self.name}, country={self.country, self.country_code}, coordinates={self.coordinates})"


class Coordinates(dict):
    def __init__(self, latitude, longitude):
        super().__init__()
        self.latitude = latitude
        self.longitude = longitude

        for k, v in vars(self).items():
            if not k.startswith("_"):
                self[k] = v

    def __repr__(self):
        return f"Coordinates(latitude={self.latitude}, longitude={self.longitude})"


