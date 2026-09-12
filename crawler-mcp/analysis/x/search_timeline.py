
import json
import os
import sys
from datetime import datetime, timedelta, timezone
import requests
from pathlib import Path
from urllib.parse import urlparse
from loguru import logger
from x_client_transaction import XClientTransaction


DEFAULT_CONFIG_PATH = Path(__file__).with_name("config.local.json")
DEFAULT_GRAPHQL_URL = (
    "https://x.com/i/api/graphql/"
    "hz_94eVAtrtQo_vO3my7Rw/SearchTimeline"
)
DEFAULT_TWEET_DETAIL_URL = (
    "https://x.com/i/api/graphql/"
    "rZA6K31W4E90vZKBmxXV3g/TweetDetail"
)
DEFAULT_CONTROLLER_DATA = (
    "DAACDAAFDAABDAABDAABCgABAAAAEgAEAAAAAAwAAgoAAQAAAAAAAAABCgAC0BlDyOUIt6I"
    "LAAMAAAAM6I2S6YeO6KGM5YuVCgAFdbGWWXScFWgIAAYAAAABCgAHccNs0VVrtJ0KAAgAAAG"
    "ffsB4hgAAAAAA"
)


def load_config():
    path = Path(os.getenv("X_CONFIG_FILE", str(DEFAULT_CONFIG_PATH))).expanduser()
    if not path.is_file():
        return {}
    config = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise RuntimeError(f"X config must be a JSON object: {path}")
    return config


def config_value(config, env_name, key, default=""):
    value = os.getenv(env_name)
    return value if value is not None else config.get(key, default)


def load_cookies(config):
    raw = os.getenv("X_COOKIES_JSON")
    cookies = json.loads(raw) if raw is not None else config.get("cookies", {})
    if not isinstance(cookies, dict):
        raise RuntimeError("cookies must be a JSON object")
    return cookies


def configure_console():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def unwrap_tweet(result):
    if not isinstance(result, dict):
        return None
    if result.get("__typename") == "TweetWithVisibilityResults":
        return result.get("tweet")
    return result if result.get("__typename") == "Tweet" else None


def iter_tweets(payload):
    timeline = payload["data"]["search_by_raw_query"]["search_timeline"]["timeline"]
    seen = set()

    for instruction in timeline.get("instructions", []):
        for entry in instruction.get("entries", []):
            content = entry.get("content", {})
            item_contents = []

            if content.get("itemContent"):
                item_contents.append(content["itemContent"])

            for module_item in content.get("items", []):
                item_content = module_item.get("item", {}).get("itemContent")
                if item_content:
                    item_contents.append(item_content)

            for item_content in item_contents:
                result = unwrap_tweet(
                    item_content.get("tweet_results", {}).get("result")
                )
                if not result:
                    continue

                tweet_id = result.get("rest_id")
                if not tweet_id or tweet_id in seen:
                    continue
                seen.add(tweet_id)
                yield result


def walk_dicts(value):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from walk_dicts(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk_dicts(item)


def iter_detail_tweets(payload):
    seen = set()
    for node in walk_dicts(payload):
        result = unwrap_tweet(node.get("tweet_results", {}).get("result"))
        if not result:
            continue
        tweet_id = result.get("rest_id")
        if not tweet_id or tweet_id in seen:
            continue
        seen.add(tweet_id)
        yield result


def find_cursor(payload, cursor_type="Bottom"):
    for node in walk_dicts(payload):
        if node.get("cursorType") == cursor_type and node.get("value"):
            return node["value"]
    return ""


def format_publish_time(value):
    if not value:
        return ""
    parsed = datetime.strptime(value, "%a %b %d %H:%M:%S %z %Y")
    china_time = parsed.astimezone(timezone(timedelta(hours=8)))
    return china_time.strftime("%Y-%m-%d %H:%M:%S %z")


def tweet_to_post(tweet):
    legacy = tweet.get("legacy", {})
    user = tweet.get("core", {}).get("user_results", {}).get("result", {})
    user_core = user.get("core", {})

    text = (
        tweet.get("note_tweet", {})
        .get("note_tweet_results", {})
        .get("result", {})
        .get("text")
        or legacy.get("full_text", "")
    )
    text = " ".join(text.split())
    screen_name = user_core.get("screen_name", "")
    tweet_id = tweet.get("rest_id") or legacy.get("id_str", "")

    return {
        "推文ID": tweet_id,
        "链接": f"https://x.com/{screen_name}/status/{tweet_id}",
        "标题/正文": text,
        "作者": user_core.get("name", ""),
        "账号": f"@{screen_name}" if screen_name else "",
        "评论数": legacy.get("reply_count", 0),
        "点赞数": legacy.get("favorite_count", 0),
        "转推数": legacy.get("retweet_count", 0),
        "浏览数": int(tweet.get("views", {}).get("count") or 0),
        "发布时间": format_publish_time(legacy.get("created_at")),
        "会话ID": legacy.get("conversation_id_str", ""),
        "回复目标ID": legacy.get("in_reply_to_status_id_str", ""),
    }


def parse_posts(payload):
    return [tweet_to_post(tweet) for tweet in iter_tweets(payload)]


def parse_comments(payload, focal_tweet_id):
    comments = []
    for tweet in iter_detail_tweets(payload):
        post = tweet_to_post(tweet)
        if post["推文ID"] == focal_tweet_id:
            continue
        if post["会话ID"] and post["会话ID"] != focal_tweet_id:
            continue
        comments.append(post)
    return comments


config = load_config()
search_config = config.get("search", {})
if not isinstance(search_config, dict):
    raise RuntimeError("search must be a JSON object")
comments_config = config.get("comments", {})
if not isinstance(comments_config, dict):
    raise RuntimeError("comments must be a JSON object")
cookies = load_cookies(config)
csrf_token = os.getenv("X_CSRF_TOKEN") or cookies.get("ct0", "")

headers = {
    "accept": "*/*",
    "accept-language": "zh-CN,zh;q=0.9",
    "authorization": config_value(config, "X_AUTHORIZATION", "authorization"),
    "content-type": "application/json",
    "priority": "u=1, i",
    "referer": "https://x.com/search?q=%E9%81%97%E5%BF%98%E4%B9%8B%E6%B5%B7&src=recent_search_click",
    "sec-ch-ua": "\"Not;A=Brand\";v=\"8\", \"Chromium\";v=\"150\", \"Google Chrome\";v=\"150\"",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": "\"Windows\"",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
    "x-client-transaction-id": "",
    "x-csrf-token": csrf_token,
    "x-twitter-active-user": "yes",
    "x-twitter-auth-type": "OAuth2Session",
    "x-twitter-client-language": "zh-cn"
}
url = config_value(
    config,
    "X_GRAPHQL_URL",
    "graphql_url",
    DEFAULT_GRAPHQL_URL,
)
if "REPLACE_CURRENT_QUERY_ID" in url:
    url = DEFAULT_GRAPHQL_URL
tweet_detail_url = comments_config.get("graphql_url") or DEFAULT_TWEET_DETAIL_URL
comments_enabled = bool(comments_config.get("enabled", False))
comment_max_posts = max(0, min(int(comments_config.get("max_posts", 3)), 20))
comment_max_pages = max(1, min(int(comments_config.get("max_pages", 1)), 20))
comment_controller_data = (
    comments_config.get("controller_data") or DEFAULT_CONTROLLER_DATA
)
search_query = os.getenv("X_SEARCH_QUERY", search_config.get("query", "遗忘之海"))
search_product = os.getenv("X_SEARCH_PRODUCT", search_config.get("product", "Top"))
query_source = os.getenv("X_QUERY_SOURCE", search_config.get("query_source", "typed_query"))
params = {
    "variables": json.dumps({
        "rawQuery": search_query,
        "count": 20,
        "querySource": query_source,
        "product": search_product,
        "withGrokTranslatedBio": True,
        "withQuickPromoteEligibilityTweetFields": False,
    }, ensure_ascii=False, separators=(",", ":")),
    "features": "{\"rweb_video_screen_enabled\":false,\"rweb_cashtags_enabled\":true,\"profile_label_improvements_pcf_label_in_post_enabled\":true,\"responsive_web_profile_redirect_enabled\":false,\"rweb_tipjar_consumption_enabled\":false,\"verified_phone_label_enabled\":false,\"creator_subscriptions_tweet_preview_api_enabled\":true,\"responsive_web_graphql_timeline_navigation_enabled\":true,\"responsive_web_graphql_skip_user_profile_image_extensions_enabled\":false,\"premium_content_api_read_enabled\":false,\"communities_web_enable_tweet_community_results_fetch\":true,\"c9s_tweet_anatomy_moderator_badge_enabled\":true,\"responsive_web_grok_analyze_button_fetch_trends_enabled\":false,\"responsive_web_grok_analyze_post_followups_enabled\":true,\"rweb_cashtags_composer_attachment_enabled\":true,\"responsive_web_jetfuel_frame\":true,\"responsive_web_grok_share_attachment_enabled\":true,\"responsive_web_grok_annotations_enabled\":true,\"articles_preview_enabled\":true,\"responsive_web_edit_tweet_api_enabled\":true,\"rweb_conversational_replies_downvote_enabled\":false,\"graphql_is_translatable_rweb_tweet_is_translatable_enabled\":true,\"view_counts_everywhere_api_enabled\":true,\"longform_notetweets_consumption_enabled\":true,\"responsive_web_twitter_article_tweet_consumption_enabled\":true,\"content_disclosure_indicator_enabled\":true,\"content_disclosure_ai_generated_indicator_enabled\":true,\"responsive_web_grok_show_grok_translated_post\":true,\"responsive_web_grok_analysis_button_from_backend\":true,\"post_ctas_fetch_enabled\":false,\"freedom_of_speech_not_reach_fetch_enabled\":true,\"standardized_nudges_misinfo\":true,\"tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled\":true,\"longform_notetweets_rich_text_read_enabled\":true,\"longform_notetweets_inline_media_enabled\":false,\"responsive_web_grok_image_annotation_enabled\":true,\"responsive_web_grok_imagine_annotation_enabled\":true,\"responsive_web_grok_community_note_auto_translation_is_enabled\":true,\"responsive_web_enhance_cards_enabled\":false}"
}
tweet_detail_field_toggles = json.dumps({
    "withArticleRichContentState": True,
    "withArticlePlainText": False,
    "withArticleSummaryText": True,
    "withArticleVoiceOver": True,
    "withGrokAnalyze": False,
    "withDisallowedReplyControls": False,
}, separators=(",", ":"))
proxy_url = config_value(config, "X_PROXY", "proxy")
proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else {}


def create_session():
    if not headers["authorization"]:
        raise RuntimeError("authorization is required in config or X_AUTHORIZATION")
    if (
        not headers["authorization"].startswith("Bearer ")
        or len(headers["authorization"]) < 80
        or "REPLACE_" in headers["authorization"]
    ):
        raise RuntimeError(
            "authorization must be the complete X Web request Authorization header, "
            "not the auth_token cookie"
        )
    if not headers["x-csrf-token"]:
        raise RuntimeError("cookies.ct0 is required (or set X_CSRF_TOKEN)")
    if not cookies.get("auth_token") or not cookies.get("ct0"):
        raise RuntimeError("cookies must contain auth_token and ct0")
    if cookies["ct0"] != headers["x-csrf-token"]:
        raise RuntimeError("csrf_token must equal the ct0 cookie")
    if not url.startswith("https://x.com/i/api/graphql/") or not url.endswith("/SearchTimeline"):
        raise RuntimeError("graphql_url must be an X SearchTimeline endpoint")

    session = requests.Session()
    session.trust_env = False
    # session.proxies.update(proxies)
    session.cookies.update(cookies)
    session.headers.update({
        "user-agent": headers["user-agent"],
        "accept-language": headers["accept-language"],
    })
    return session


def generate_transaction_header(transaction, request_url):
    transaction_id = transaction.generate(
        method="GET",
        path=urlparse(request_url).path,
    )
    return transaction_id


def request_search(session, transaction):
    request_headers = dict(headers)
    request_headers["x-client-transaction-id"] = generate_transaction_header(
        transaction, url
    )
    response = session.get(
        url,
        headers=request_headers,
        cookies=cookies,
        params=params,
        timeout=20,
    )
    response.raise_for_status()
    return response


def tweet_detail_params(tweet_id, cursor=None):
    variables = {
        "focalTweetId": tweet_id,
        "referrer": "search",
        "controller_data": comment_controller_data,
        "with_rux_injections": False,
        "rankingMode": "Relevance",
        "includePromotedContent": True,
        "withCommunity": True,
        "withQuickPromoteEligibilityTweetFields": True,
        "withBirdwatchNotes": True,
        "withVoice": True,
    }
    if cursor:
        variables["cursor"] = cursor
    return {
        "variables": json.dumps(variables, separators=(",", ":")),
        "features": params["features"],
        "fieldToggles": tweet_detail_field_toggles,
    }


def fetch_comments(session, transaction, tweet_id):
    comments = []
    seen_ids = set()
    cursor = None
    seen_cursors = set()

    for _ in range(comment_max_pages):
        request_headers = dict(headers)
        request_headers["referer"] = f"https://x.com/i/status/{tweet_id}"
        request_headers["x-client-transaction-id"] = generate_transaction_header(
            transaction, tweet_detail_url
        )
        response = session.get(
            tweet_detail_url,
            headers=request_headers,
            cookies=cookies,
            params=tweet_detail_params(tweet_id, cursor),
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()

        for comment in parse_comments(payload, tweet_id):
            comment_id = comment["推文ID"]
            if comment_id and comment_id not in seen_ids:
                seen_ids.add(comment_id)
                comments.append(comment)

        next_cursor = find_cursor(payload)
        if not next_cursor or next_cursor in seen_cursors:
            break
        seen_cursors.add(next_cursor)
        cursor = next_cursor

    return comments


def save_results(response, posts):
    response_path = Path(__file__).with_name("搜索动态响应.json")
    response_path.write_text(response.text, encoding="utf-8")

    posts_path = Path(__file__).with_name("搜索帖子.json")
    posts_path.write_text(
        json.dumps(posts, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return response_path, posts_path


def print_results(response, posts, response_path, posts_path):
    logger.info(f"HTTP {response.status_code}")
    logger.info(f"Content-Type: {response.headers.get('content-type')}")
    logger.info(f"响应已保存: {response_path}")
    logger.info(f"帖子已保存: {posts_path}")
    logger.info(f"帖子数量: {len(posts)}")

    for index, post in enumerate(posts, 1):
        logger.info("\n" + "=" * 88)
        logger.info(f"[{index}] {post['标题/正文']}")
        logger.info(f"作者: {post['作者']} ({post['账号']})")
        logger.info(f"发布时间: {post['发布时间']}")
        logger.info(f"评论数: {post['评论数']} | 点赞数: {post['点赞数']}")
        if "实际评论数" in post:
            logger.info(f"实际抓取评论: {post['实际评论数']}")
        if post.get("评论错误"):
            logger.warning(f"评论抓取失败: {post['评论错误']}")
        logger.info(f"链接: {post['链接']}")


def main():
    configure_console()
    session = create_session()
    transaction = XClientTransaction.from_session(session)
    logger.info(f"animation-key: {transaction.animation_key}")
    logger.info(
        f"评论抓取: {'开启' if comments_enabled else '关闭'} | "
        f"帖子上限: {comment_max_posts} | 每帖页数: {comment_max_pages}"
    )

    response = request_search(session, transaction)
    posts = parse_posts(response.json())
    if comments_enabled:
        for index, post in enumerate(posts[:comment_max_posts], 1):
            tweet_id = post["推文ID"]
            logger.info(f"抓取评论 [{index}/{min(len(posts), comment_max_posts)}]: {tweet_id}")
            try:
                post["评论"] = fetch_comments(session, transaction, tweet_id)
                post["实际评论数"] = len(post["评论"])
            except Exception as exc:
                post["评论"] = []
                post["评论错误"] = f"{type(exc).__name__}: {exc}"
    response_path, posts_path = save_results(response, posts)
    print_results(response, posts, response_path, posts_path)


if __name__ == "__main__":
    main()
