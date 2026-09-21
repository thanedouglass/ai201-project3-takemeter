import pandas as pd
import requests


def fetch_katseye_data(subreddit="katseyesnark_", target_count=220):
    posts = []
    seen_texts = set()

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) TakeMeterDataCollector/1.0"
    }

    # 1. Fetch Posts from Arctic Shift
    print(f"Fetching POSTS from r/{subreddit}...")
    try:
        url = "https://arctic-shift.photon-reddit.com/api/posts/search"
        res = requests.get(
            url,
            params={"subreddit": subreddit, "limit": 100},
            headers=headers,
            timeout=10,
        )
        if res.status_code == 200:
            for item in res.json().get("data", []):
                title = item.get("title", "")
                body = item.get("selftext", "")
                text = f"{title} {body}".strip()
                if (
                    len(text) > 25
                    and "[removed]" not in text
                    and "[deleted]" not in text
                ):
                    if text not in seen_texts:
                        seen_texts.add(text)
                        posts.append({"text": text, "label": ""})
    except Exception as e:
        print(f"Posts fetch note: {e}")

    print(
        f"Fetched {len(posts)} posts. Now fetching COMMENTS from r/{subreddit}..."
    )

    # 2. Fetch Comments from Arctic Shift
    try:
        url = "https://arctic-shift.photon-reddit.com/api/comments/search"
        res = requests.get(
            url,
            params={"subreddit": subreddit, "limit": 100},
            headers=headers,
            timeout=10,
        )
        if res.status_code == 200:
            for item in res.json().get("data", []):
                text = item.get("body", "").strip()
                if (
                    len(text) > 30
                    and "[removed]" not in text
                    and "[deleted]" not in text
                ):
                    if text not in seen_texts:
                        seen_texts.add(text)
                        posts.append({"text": text, "label": ""})
    except Exception as e:
        print(f"Comments fetch note: {e}")

    # 3. Fallback to PullPush API if more items are needed
    if len(posts) < target_count:
        print(
            f"Currently at {len(posts)} items. Pulling additional comments from PullPush..."
        )
        try:
            url = "https://api.pullpush.io/reddit/search/comment/"
            res = requests.get(
                url,
                params={"subreddit": subreddit, "size": 100},
                headers=headers,
                timeout=10,
            )
            if res.status_code == 200:
                for item in res.json().get("data", []):
                    text = item.get("body", "").strip()
                    if (
                        len(text) > 30
                        and "[removed]" not in text
                        and "[deleted]" not in text
                    ):
                        if text not in seen_texts:
                            seen_texts.add(text)
                            posts.append({"text": text, "label": ""})
        except Exception as e:
            print(f"PullPush fetch note: {e}")

    df = pd.DataFrame(posts[:target_count])
    df.to_csv("dataset.csv", index=False)
    print(
        f"SUCCESS! Saved {len(df)} unique items (posts + comments) to dataset.csv."
    )


if __name__ == "__main__":
    fetch_katseye_data("katseyesnark_")