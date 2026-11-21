"""
WORKER 4: THE POSTER
Posts post.txt (text) and card.png (picture) to your personal LinkedIn profile.

Needs:   your LinkedIn access token in the LINKEDIN_ACCESS_TOKEN variable
Test:    python poster.py --dry-run     (checks everything, posts NOTHING)
Post:    python poster.py
"""

import os
import sys

import requests

# ---- SETTINGS YOU CAN CHANGE ------------------------------------------
LINKEDIN_VERSION = "202605"      # LinkedIn API version (YYYYMM). If LinkedIn says the version
                                 # doesn't exist, tell me and I'll give you a newer one.
VISIBILITY = "PUBLIC"            # "PUBLIC" or "CONNECTIONS"
POST_FILE = "post.txt"
IMAGE_FILE = "card.png"
IMAGE_TITLE = "Market Wrap"
IMAGE_ALT = ("Scoreboard of the last trading session's moves in global stock markets, "
             "bond yields, currencies, gold and oil.")
TIMEOUT = 60
# -----------------------------------------------------------------------

API = "https://api.linkedin.com"
# Characters LinkedIn treats as special code in post text. Each must get a backslash.
RESERVED = set("\\|{}@[]()<>#*_~")


def escape_for_linkedin(text):
    return "".join("\\" + ch if ch in RESERVED else ch for ch in text)


def fail(message, response=None):
    print(f"\nSTOPPED: {message}")
    if response is not None:
        print(f"LinkedIn said: {response.status_code} {response.text[:400]}")
        if response.status_code == 401:
            print("Hint: the token is wrong or expired. Generate a new one and enter it again.")
        elif response.status_code == 403:
            print("Hint: the token is missing a permission (w_member_social), or the product "
                  "isn't approved on your app.")
        elif "VERSION" in response.text.upper():
            print("Hint: change LINKEDIN_VERSION at the top of poster.py and tell me what it says.")
    sys.exit(1)


def rest_headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "LinkedIn-Version": LINKEDIN_VERSION,
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json",
    }


def get_member(token):
    """Ask LinkedIn who the token belongs to. Returns (name, author_urn)."""
    r = requests.get(f"{API}/v2/userinfo", headers={"Authorization": f"Bearer {token}"},
                     timeout=TIMEOUT)
    if r.status_code != 200:
        fail("Could not check your LinkedIn login with this token.", r)
    info = r.json()
    return info.get("name", "(name not shown)"), f"urn:li:person:{info['sub']}"


def upload_image(token, author, path):
    r = requests.post(f"{API}/rest/images?action=initializeUpload",
                      headers=rest_headers(token),
                      json={"initializeUploadRequest": {"owner": author}}, timeout=TIMEOUT)
    if r.status_code not in (200, 201):
        fail("Could not start the picture upload.", r)
    value = r.json()["value"]
    with open(path, "rb") as f:
        up = requests.put(value["uploadUrl"], data=f.read(),
                          headers={"Authorization": f"Bearer {token}",
                                   "Content-Type": "application/octet-stream"},
                          timeout=TIMEOUT)
    if up.status_code not in (200, 201):
        fail("The picture upload failed.", up)
    return value["image"]


def create_post(token, author, commentary, image_urn):
    body = {
        "author": author,
        "commentary": commentary,
        "visibility": VISIBILITY,
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "content": {"media": {"title": IMAGE_TITLE, "altText": IMAGE_ALT, "id": image_urn}},
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }
    r = requests.post(f"{API}/rest/posts", headers=rest_headers(token), json=body,
                      timeout=TIMEOUT)
    if r.status_code != 201:
        fail("LinkedIn did not accept the post.", r)
    return r.headers.get("x-restli-id", "")


def main():
    dry_run = "--dry-run" in sys.argv

    token = os.environ.get("LINKEDIN_ACCESS_TOKEN", "").strip()
    if not token:
        sys.exit("No LINKEDIN_ACCESS_TOKEN found. Enter your token in this Terminal window first.")

    try:
        with open(POST_FILE, encoding="utf-8") as f:
            text = f.read().strip()
    except FileNotFoundError:
        sys.exit(f"{POST_FILE} not found. Run  python writer.py  first.")
    if not os.path.exists(IMAGE_FILE):
        sys.exit(f"{IMAGE_FILE} not found. Run  python artist.py  first.")
    if not text:
        sys.exit(f"{POST_FILE} is empty.")
    if len(text) > 3000:
        sys.exit(f"The post is {len(text)} characters. LinkedIn's limit is 3,000.")

    name, author = get_member(token)
    print(f"Token works. Logged in as: {name}")

    commentary = escape_for_linkedin(text)
    size_kb = os.path.getsize(IMAGE_FILE) // 1024

    if dry_run:
        print("\n----- POST TEXT (as it will be posted) -----")
        print(text)
        print("----- END -----")
        print(f"\n{len(text)} characters. Picture: {IMAGE_FILE} ({size_kb} KB). Visibility: {VISIBILITY}.")
        print("DRY RUN ONLY: nothing was posted.")
        return

    print("Uploading the picture...")
    image_urn = upload_image(token, author, IMAGE_FILE)
    print("Creating the post...")
    post_urn = create_post(token, author, commentary, image_urn)
    print("\nPosted!")
    if post_urn:
        print(f"Open it: https://www.linkedin.com/feed/update/{post_urn}/")


if __name__ == "__main__":
    main()
