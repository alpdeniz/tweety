from tweety.bot import Tweety


def test_get_user():
    tweety = Tweety()
    user = tweety.get_user('elonmusk')
    print(user.name, user.id, user.username)
    assert user.rest_id == '44196397'
    assert user.username == 'elonmusk'