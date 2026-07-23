"""One-time: refresh the Etsy OAuth access token via the stored refresh_token,
and write the new access_token (and rotated refresh_token, if issued) back to .env.
"""
from pipeline import config
from pipeline import etsy_auth


def main():
    config.load_env()
    result = etsy_auth.refresh()
    print(f"refreshed: expires_in={result['expires_in']}s, "
          f"refresh_token_rotated={result['rotated']}")


if __name__ == "__main__":
    main()
