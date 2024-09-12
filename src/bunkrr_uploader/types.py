from typing import List, TypedDict
from datetime import datetime


class ChunkSize(TypedDict):
    max: str
    default: str
    timeout: int


class FileIdentifierLength(TypedDict):
    min: int
    max: int
    default: int
    force: bool


class StripTags(TypedDict):
    default: bool
    video: bool
    force: bool
    blacklistExtensions: List[str]


class CheckResponse(TypedDict):
    private: bool
    enableUserAccounts: bool
    maxSize: str
    chunkSize: ChunkSize
    fileIdentifierLength: FileIdentifierLength
    stripTags: StripTags
    temporaryUploadAges: List[int]
    defaultTemporaryUploadAge: int


class NodeResponse(TypedDict):
    success: bool
    url: str


class Permissions(TypedDict):
    user: bool
    vip: bool
    vvip: bool
    moderator: bool
    admin: bool
    superadmin: bool


class VerifyTokenResponse(TypedDict):
    success: bool
    username: str
    permissions: Permissions
    group: str
    retentionPeriods: List[int]
    defaultRetentionPeriod: int


class File(TypedDict):
    name: str
    url: str
    # The are hacked on and not officially there from the API
    original: str
    albumid: str
    filePathMD5: str
    fileNameMD5: str
    uploadSuccess: str


# This is the same for finish chunks
class UploadResponse(TypedDict):
    success: bool
    files: List[File]


class CreateAlbumResponse(TypedDict):
    success: bool
    id: int


class Album(TypedDict):
    id: int
    name: str
    identifier: str
    enabled: int
    timestamp: int
    editedAt: int
    zipGeneratedAt: int
    download: bool
    public: bool
    description: str
    uploads: int
    size: int
    zipSize: None
    descriptionHtml: str


class GetAlbumsResponse(TypedDict):
    success: bool
    albums: List[Album]
    count: int
    homeDomain: str


class AlbumFileItem(TypedDict):
    id: int
    name: str
    original: str
    userid: int
    size: str
    timestamp: int
    slug: str
    type: str
    last_visited_at: str
    expirydate: None
    albumid: int
    node_id: int
    cdn: str
    extname: str
    basedomain: str
    finalurl: str
    thumb: str


class GetAlbumResponse(TypedDict):
    success: bool
    files: List[AlbumFileItem]
    count: int
    albums: dict[str, str]
    basedomain: str

