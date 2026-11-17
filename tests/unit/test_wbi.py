"""Tests for WBI signature."""

import hashlib

from bili_sub2txt.bilibili.wbi import MIXIN_KEY_ENC_TAB, get_mixin_key, sign


class TestMixinKeyEncTab:
    def test_length_is_64(self):
        assert len(MIXIN_KEY_ENC_TAB) == 64

    def test_values_in_range(self):
        assert all(0 <= i < 64 for i in MIXIN_KEY_ENC_TAB)

    def test_is_permutation(self):
        assert sorted(MIXIN_KEY_ENC_TAB) == list(range(64))


class TestGetMixinKey:
    def test_known_vector(self):
        # Vector from Bilibili wiki documentation.
        img_key = "7cd084941338484aae1ad9425b84077c"
        sub_key = "4932caff0ff746eab6f01bf08b70ac45"
        mixin = get_mixin_key(img_key, sub_key)
        assert len(mixin) == 32
        # The mixin key is deterministic.
        assert mixin == get_mixin_key(img_key, sub_key)


class TestSign:
    def test_includes_w_rid_and_wts(self):
        params = {"aid": 123, "cid": 456}
        signed = sign(params, "a" * 32, "b" * 32)
        assert "w_rid" in signed
        assert "wts" in signed
        assert signed["aid"] == "123"
        assert signed["cid"] == "456"

    def test_deterministic(self):
        params = {"aid": 123}
        s1 = sign(params, "a" * 32, "b" * 32, wts=1700000000)
        s2 = sign(params, "a" * 32, "b" * 32, wts=1700000000)
        assert s1["w_rid"] == s2["w_rid"]

    def test_filters_special_chars(self):
        params = {"foo": "a!'()*b"}
        signed = sign(params, "a" * 32, "b" * 32, wts=0)
        assert signed["foo"] == "ab"

    def test_w_rid_is_md5(self):
        params = {"aid": 1}
        signed = sign(params, "a" * 32, "b" * 32, wts=0)
        # Reconstruct the query to verify w_rid.
        mixin = get_mixin_key("a" * 32, "b" * 32)
        query = "&".join(f"{k}={signed[k]}" for k in sorted(signed) if k != "w_rid")
        expected = hashlib.md5((query + mixin).encode()).hexdigest()
        assert signed["w_rid"] == expected
