"""ROM extraction, source parsing, asset loading, and image inspection helpers."""
from zelda_suite.extract.asset_loader import (
    ASSET_REGISTRY_FORMAT,
    DICTIONARY_INVENTORY_FORMAT,
    ITEM_RECEIPT_LAYOUT_FORMAT,
    MUSIC_TRACK_INDEX_FORMAT,
    SPRITE_DISPATCH_FORMAT,
    TEXT_MESSAGE_INDEX_FORMAT,
    AssetLoadError,
    list_extracted_assets,
    load_extracted_asset,
    load_source_export,
    validate_source_export,
)
from zelda_suite.extract.data_table import (
    DATA_DIRECTIVE_WIDTHS,
    DataTableEntry,
    DataTableParseError,
    parse_data_table,
)
from zelda_suite.extract.dictionary_inventory import (
    DictionaryFragment,
    DictionaryInventoryError,
    parse_dictionary_fragment_inventory,
)
from zelda_suite.extract.disassembly import (
    POINTER_DIRECTIVE_WIDTHS,
    DisassemblyParseError,
    PointerTableEntry,
    parse_dl_pointer_table,
    parse_dw_pointer_table,
    parse_source_pointer_table,
)
from zelda_suite.extract.dungeon_room_pointer_verification import (
    DungeonRoomPointerVerificationError,
    verify_dungeon_room_pointers,
)
from zelda_suite.extract.incbin_inventory import (
    IncbinDeclaration,
    IncbinInventoryError,
    parse_incbin_inventory,
)
from zelda_suite.extract.incbin_inventory_audit import (
    INCBIN_INVENTORY_AUDIT_FORMAT,
    IncbinInventoryAuditError,
    audit_incbin_inventories,
)
from zelda_suite.extract.item_receipt_layout import (
    ItemReceiptLayoutError,
    build_item_receipt_layout,
)
from zelda_suite.extract.music_track_index import (
    MusicTrackEntry,
    MusicTrackIndex,
    MusicTrackIndexError,
    parse_music_track_index,
)
from zelda_suite.extract.overworld_hidden_item_verification import (
    PINNED_SOURCE_REVISION,
    OverworldHiddenItemVerificationError,
    parse_overworld_hidden_item_source,
    verify_overworld_hidden_items,
)
from zelda_suite.extract.overworld_payload_pairs import (
    OverworldPayloadPairError,
    validate_overworld_payload_pairs,
)
from zelda_suite.extract.rom_image import (
    ROMImageInspection,
    ROMImageInspectionError,
    format_lorom_cpu_address,
    inspect_rom_image,
    lorom_cpu_address,
    read_rom_bytes,
    sha256_rom_bytes,
)
from zelda_suite.extract.rom_table_verification import (
    ROM_TABLE_VERIFICATION_FORMAT,
    ROMTableVerificationError,
    verify_registered_scalar_tables,
)
from zelda_suite.extract.sprite_dispatch import (
    SpriteDispatchEntry,
    SpriteDispatchParseError,
    SpriteDispatchTable,
    parse_sprite_dispatch_table,
)
from zelda_suite.extract.text_message_index import (
    MessageSourceBlock,
    TextMessageBlockRecord,
    TextMessageIndex,
    TextMessageIndexError,
    TextMessageRecord,
    parse_text_message_index,
)

__all__ = [
    "ASSET_REGISTRY_FORMAT",
    "DATA_DIRECTIVE_WIDTHS",
    "DICTIONARY_INVENTORY_FORMAT",
    "INCBIN_INVENTORY_AUDIT_FORMAT",
    "ITEM_RECEIPT_LAYOUT_FORMAT",
    "MUSIC_TRACK_INDEX_FORMAT",
    "PINNED_SOURCE_REVISION",
    "POINTER_DIRECTIVE_WIDTHS",
    "ROM_TABLE_VERIFICATION_FORMAT",
    "SPRITE_DISPATCH_FORMAT",
    "TEXT_MESSAGE_INDEX_FORMAT",
    "AssetLoadError",
    "DataTableEntry",
    "DataTableParseError",
    "DictionaryFragment",
    "DictionaryInventoryError",
    "DisassemblyParseError",
    "DungeonRoomPointerVerificationError",
    "IncbinDeclaration",
    "IncbinInventoryAuditError",
    "IncbinInventoryError",
    "ItemReceiptLayoutError",
    "MessageSourceBlock",
    "MusicTrackEntry",
    "MusicTrackIndex",
    "MusicTrackIndexError",
    "OverworldHiddenItemVerificationError",
    "OverworldPayloadPairError",
    "PointerTableEntry",
    "ROMImageInspection",
    "ROMImageInspectionError",
    "ROMTableVerificationError",
    "SpriteDispatchEntry",
    "SpriteDispatchParseError",
    "SpriteDispatchTable",
    "TextMessageBlockRecord",
    "TextMessageIndex",
    "TextMessageIndexError",
    "TextMessageRecord",
    "audit_incbin_inventories",
    "build_item_receipt_layout",
    "format_lorom_cpu_address",
    "inspect_rom_image",
    "list_extracted_assets",
    "load_extracted_asset",
    "load_source_export",
    "lorom_cpu_address",
    "parse_data_table",
    "parse_dictionary_fragment_inventory",
    "parse_dl_pointer_table",
    "parse_dw_pointer_table",
    "parse_incbin_inventory",
    "parse_music_track_index",
    "parse_overworld_hidden_item_source",
    "parse_source_pointer_table",
    "parse_sprite_dispatch_table",
    "parse_text_message_index",
    "read_rom_bytes",
    "sha256_rom_bytes",
    "validate_overworld_payload_pairs",
    "validate_source_export",
    "verify_dungeon_room_pointers",
    "verify_overworld_hidden_items",
    "verify_registered_scalar_tables",
]
