from typing import List, TypedDict


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


class AlbumItemResponse(TypedDict):
    id: int
    name: str
    identifier: str


class AlbumsResponse(TypedDict):
    success: bool
    albums: List[AlbumItemResponse]
    count: int


class CreateAlbumResponse(TypedDict):
    success: bool
    id: int
