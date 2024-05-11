import argparse
import os
from pathlib import Path


def cli():
    parser = argparse.ArgumentParser(prog="bunkrr-upload", description="Bunkrr Uploader supporting parallel uploads")
    parser.add_argument("file", type=Path, help="File or directory to look for files in to upload")
    parser.add_argument(
        "-t",
        "--token",
        type=str,
        default=os.getenv("BUNKRR_TOKEN"),
        help="""API token for your account so that you can upload to a specific account/folder.
                You can also set the BUNKRR_TOKEN environment variable for this""",
    )
    parser.add_argument(
        "-f", "--folder", type=str, help="Folder to upload files to overriding the directory name if used"
    )
    parser.add_argument(
        "-d",
        "--dry-run",
        action="store_true",
        help="Don't create folders or upload files",
    )
    parser.add_argument(
        "--max-chunk-size",
        action="store_true",
        help="Use the server's maximum chunk size instead of the default one",
    )
    parser.add_argument("-c", "--connections", type=int, default=2, help="Maximum parallel uploads to do at once")
    parser.add_argument(
        "--public",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Make all files uploaded public. By default they are private and not unsharable",
    )
    parser.add_argument(
        "--save",
        action=argparse.BooleanOptionalAction,
        default=True,
        help='Don\'t save uploaded file urls to a "gofile_upload_<unixtime>.csv" file',
    )
    parser.add_argument(
        "--use-config",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Whether to create and use a config file in $HOME/.config/gofile_upload/config.json",
    )
    parser.add_argument(
        "-r",
        "--retries",
        default=1,
        type=int,
        help="How many times to retry a failed upload",
    )
    parser.add_argument(
        "--chunk-retries",
        default=1,
        type=int,
        help="How many times to retry a failed chunk or chunk completion",
    )
    args = parser.parse_args()

    return args
