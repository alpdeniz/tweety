from tweety.bot import Tweety
from tweety.exceptions_ import UserProtected
import pytest

@pytest.mark.skip
def test_protected_user():
    tweety = Tweety()
    try:
        tweety.get_user('protected_account')
    except UserProtected:
        assert True
        return 
    except Exception:
        pass
    assert False
    