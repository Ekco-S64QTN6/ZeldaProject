"""ROM extraction, source parsing, asset loading, and image inspection helpers."""
from zelda_suite.extract.asset_loader import (
    ASSET_REGISTRY_FORMAT,
    DICTIONARY_INVENTORY_FORMAT,
    DUNGEON_CHEST_DATA_FORMAT,
    ITEM_RECEIPT_LAYOUT_FORMAT,
    MIXED_DATA_TABLE_FORMAT,
    MUSIC_TRACK_INDEX_FORMAT,
    PAID_OVERWORLD_INTERACTIONS_FORMAT,
    POTION_SHOP_TRANSACTIONS_FORMAT,
    SHOP_ITEM_HANDLERS_FORMAT,
    SPECIAL_SHOP_TRANSACTIONS_FORMAT,
    SPRITE_DISPATCH_FORMAT,
    SPRITE_PREP_DISPATCH_FORMAT,
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
from zelda_suite.extract.dungeon_chest_data import (
    DungeonChestDataEntry,
    DungeonChestDataParseError,
    DungeonChestDataTable,
    parse_dungeon_chest_data,
)
from zelda_suite.extract.dungeon_chest_data_audit import (
    DUNGEON_CHEST_DATA_AUDIT_FORMAT,
    DungeonChestDataAuditError,
    audit_dungeon_chest_data,
)
from zelda_suite.extract.dungeon_room_asset_audit import (
    DUNGEON_ROOM_ASSET_AUDIT_FORMAT,
    DungeonRoomAssetAuditError,
    audit_dungeon_room_assets,
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
from zelda_suite.extract.item_receipt_annotation_audit import (
    ITEM_RECEIPT_ANNOTATION_AUDIT_FORMAT,
    ItemReceiptAnnotationAuditError,
    audit_item_receipt_annotations,
)
from zelda_suite.extract.item_receipt_layout import (
    ItemReceiptLayoutError,
    build_item_receipt_layout,
)
from zelda_suite.extract.mixed_data_table import (
    MixedDataField,
    MixedDataRecord,
    MixedDataTable,
    MixedDataTableParseError,
    parse_mixed_data_table,
)
from zelda_suite.extract.music_asset_audit import (
    MUSIC_ASSET_AUDIT_FORMAT,
    MusicAssetAuditError,
    audit_music_assets,
)
from zelda_suite.extract.music_track_index import (
    MusicTrackEntry,
    MusicTrackIndex,
    MusicTrackIndexError,
    parse_music_track_index,
)
from zelda_suite.extract.oam_allocation_audit import (
    OAM_ALLOCATION_AUDIT_FORMAT,
    OAMAllocationAuditError,
    audit_oam_allocation,
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
from zelda_suite.extract.paid_overworld_interactions import (
    PaidOverworldInteractionsParseError,
    parse_paid_overworld_interactions,
)
from zelda_suite.extract.paid_overworld_interactions_audit import (
    PAID_OVERWORLD_INTERACTIONS_AUDIT_FORMAT,
    PaidOverworldInteractionsAuditError,
    audit_paid_overworld_interactions,
)
from zelda_suite.extract.potion_shop_transactions import (
    PotionShopTransactionEntry,
    PotionShopTransactionsParseError,
    PotionShopTransactionsTable,
    parse_potion_shop_transactions,
)
from zelda_suite.extract.potion_shop_transactions_audit import (
    POTION_SHOP_TRANSACTIONS_AUDIT_FORMAT,
    PotionShopTransactionsAuditError,
    audit_potion_shop_transactions,
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
from zelda_suite.extract.shop_item_handlers import (
    ShopItemHandlerEntry,
    ShopItemHandlersParseError,
    ShopItemHandlersTable,
    parse_shop_item_handlers,
)
from zelda_suite.extract.shop_item_handlers_audit import (
    SHOP_ITEM_HANDLERS_AUDIT_FORMAT,
    ShopItemHandlersAuditError,
    audit_shop_item_handlers,
)
from zelda_suite.extract.source_expression_audit import (
    SOURCE_EXPRESSION_AUDIT_FORMAT,
    SourceExpressionAuditError,
    audit_unresolved_table_expressions,
)
from zelda_suite.extract.special_shop_transactions import (
    SpecialShopTransactionEntry,
    SpecialShopTransactionsParseError,
    SpecialShopTransactionsTable,
    parse_special_shop_transactions,
)
from zelda_suite.extract.special_shop_transactions_audit import (
    SPECIAL_SHOP_TRANSACTIONS_AUDIT_FORMAT,
    SpecialShopTransactionsAuditError,
    audit_special_shop_transactions,
)
from zelda_suite.extract.sprite_dispatch import (
    SpriteDispatchEntry,
    SpriteDispatchParseError,
    SpriteDispatchTable,
    parse_sprite_dispatch_table,
)
from zelda_suite.extract.sprite_prep_dispatch import (
    SpritePrepDispatchEntry,
    SpritePrepDispatchParseError,
    SpritePrepDispatchTable,
    parse_sprite_prep_dispatch_table,
)
from zelda_suite.extract.sprite_prep_dispatch_audit import (
    SPRITE_PREP_DISPATCH_AUDIT_FORMAT,
    SpritePrepDispatchAuditError,
    audit_sprite_prep_dispatch,
)
from zelda_suite.extract.text_dictionary_audit import (
    TEXT_DICTIONARY_AUDIT_FORMAT,
    TextDictionaryAuditError,
    audit_text_dictionary_assets,
)
from zelda_suite.extract.text_dictionary_pointer_verification import (
    TEXT_DICTIONARY_POINTER_VERIFICATION_FORMAT,
    TextDictionaryPointerVerificationError,
    verify_text_dictionary_pointers,
)
from zelda_suite.extract.text_message_byte_verification import (
    PINNED_TEXT_SOURCE_REVISION,
    TEXT_MESSAGE_BYTE_VERIFICATION_FORMAT,
    TextMessageByteVerificationError,
    default_text_message_source_blocks,
    verify_text_message_bytes,
)
from zelda_suite.extract.text_message_index import (
    MessageSourceBlock,
    TextMessageBlockRecord,
    TextMessageIndex,
    TextMessageIndexError,
    TextMessageRecord,
    parse_text_message_index,
)
from zelda_suite.extract.text_message_index_audit import (
    TEXT_MESSAGE_INDEX_AUDIT_FORMAT,
    TextMessageIndexAuditError,
    audit_text_message_index,
)

__all__ = [
    "ASSET_REGISTRY_FORMAT",
    "AssetLoadError",
    "audit_dungeon_chest_data",
    "audit_dungeon_room_assets",
    "audit_incbin_inventories",
    "audit_item_receipt_annotations",
    "audit_music_assets",
    "audit_oam_allocation",
    "audit_paid_overworld_interactions",
    "audit_potion_shop_transactions",
    "audit_shop_item_handlers",
    "audit_special_shop_transactions",
    "audit_sprite_prep_dispatch",
    "audit_text_dictionary_assets",
    "audit_text_message_index",
    "audit_unresolved_table_expressions",
    "build_item_receipt_layout",
    "DATA_DIRECTIVE_WIDTHS",
    "DataTableEntry",
    "DataTableParseError",
    "default_text_message_source_blocks",
    "DICTIONARY_INVENTORY_FORMAT",
    "DictionaryFragment",
    "DictionaryInventoryError",
    "DisassemblyParseError",
    "DUNGEON_CHEST_DATA_AUDIT_FORMAT",
    "DUNGEON_CHEST_DATA_FORMAT",
    "DUNGEON_ROOM_ASSET_AUDIT_FORMAT",
    "DungeonChestDataAuditError",
    "DungeonChestDataEntry",
    "DungeonChestDataParseError",
    "DungeonChestDataTable",
    "DungeonRoomAssetAuditError",
    "DungeonRoomPointerVerificationError",
    "format_lorom_cpu_address",
    "INCBIN_INVENTORY_AUDIT_FORMAT",
    "IncbinDeclaration",
    "IncbinInventoryAuditError",
    "IncbinInventoryError",
    "inspect_rom_image",
    "ITEM_RECEIPT_ANNOTATION_AUDIT_FORMAT",
    "ITEM_RECEIPT_LAYOUT_FORMAT",
    "ItemReceiptAnnotationAuditError",
    "ItemReceiptLayoutError",
    "list_extracted_assets",
    "load_extracted_asset",
    "load_source_export",
    "lorom_cpu_address",
    "MessageSourceBlock",
    "MIXED_DATA_TABLE_FORMAT",
    "MixedDataField",
    "MixedDataRecord",
    "MixedDataTable",
    "MixedDataTableParseError",
    "MUSIC_ASSET_AUDIT_FORMAT",
    "MUSIC_TRACK_INDEX_FORMAT",
    "MusicAssetAuditError",
    "MusicTrackEntry",
    "MusicTrackIndex",
    "MusicTrackIndexError",
    "OAM_ALLOCATION_AUDIT_FORMAT",
    "OAMAllocationAuditError",
    "OverworldHiddenItemVerificationError",
    "OverworldPayloadPairError",
    "PAID_OVERWORLD_INTERACTIONS_AUDIT_FORMAT",
    "PAID_OVERWORLD_INTERACTIONS_FORMAT",
    "PaidOverworldInteractionsAuditError",
    "PaidOverworldInteractionsParseError",
    "parse_data_table",
    "parse_dictionary_fragment_inventory",
    "parse_dl_pointer_table",
    "parse_dungeon_chest_data",
    "parse_dw_pointer_table",
    "parse_incbin_inventory",
    "parse_mixed_data_table",
    "parse_music_track_index",
    "parse_overworld_hidden_item_source",
    "parse_paid_overworld_interactions",
    "parse_potion_shop_transactions",
    "parse_shop_item_handlers",
    "parse_source_pointer_table",
    "parse_special_shop_transactions",
    "parse_sprite_dispatch_table",
    "parse_sprite_prep_dispatch_table",
    "parse_text_message_index",
    "PINNED_SOURCE_REVISION",
    "PINNED_TEXT_SOURCE_REVISION",
    "POINTER_DIRECTIVE_WIDTHS",
    "PointerTableEntry",
    "POTION_SHOP_TRANSACTIONS_AUDIT_FORMAT",
    "POTION_SHOP_TRANSACTIONS_FORMAT",
    "PotionShopTransactionEntry",
    "PotionShopTransactionsAuditError",
    "PotionShopTransactionsParseError",
    "PotionShopTransactionsTable",
    "read_rom_bytes",
    "ROM_TABLE_VERIFICATION_FORMAT",
    "ROMImageInspection",
    "ROMImageInspectionError",
    "ROMTableVerificationError",
    "sha256_rom_bytes",
    "SHOP_ITEM_HANDLERS_AUDIT_FORMAT",
    "SHOP_ITEM_HANDLERS_FORMAT",
    "ShopItemHandlerEntry",
    "ShopItemHandlersAuditError",
    "ShopItemHandlersParseError",
    "ShopItemHandlersTable",
    "SOURCE_EXPRESSION_AUDIT_FORMAT",
    "SourceExpressionAuditError",
    "SPECIAL_SHOP_TRANSACTIONS_AUDIT_FORMAT",
    "SPECIAL_SHOP_TRANSACTIONS_FORMAT",
    "SpecialShopTransactionEntry",
    "SpecialShopTransactionsAuditError",
    "SpecialShopTransactionsParseError",
    "SpecialShopTransactionsTable",
    "SPRITE_DISPATCH_FORMAT",
    "SPRITE_PREP_DISPATCH_AUDIT_FORMAT",
    "SPRITE_PREP_DISPATCH_FORMAT",
    "SpriteDispatchEntry",
    "SpriteDispatchParseError",
    "SpriteDispatchTable",
    "SpritePrepDispatchAuditError",
    "SpritePrepDispatchEntry",
    "SpritePrepDispatchParseError",
    "SpritePrepDispatchTable",
    "TEXT_DICTIONARY_AUDIT_FORMAT",
    "TEXT_DICTIONARY_POINTER_VERIFICATION_FORMAT",
    "TEXT_MESSAGE_BYTE_VERIFICATION_FORMAT",
    "TEXT_MESSAGE_INDEX_AUDIT_FORMAT",
    "TEXT_MESSAGE_INDEX_FORMAT",
    "TextDictionaryAuditError",
    "TextDictionaryPointerVerificationError",
    "TextMessageBlockRecord",
    "TextMessageByteVerificationError",
    "TextMessageIndex",
    "TextMessageIndexAuditError",
    "TextMessageIndexError",
    "TextMessageRecord",
    "validate_overworld_payload_pairs",
    "validate_source_export",
    "verify_dungeon_room_pointers",
    "verify_overworld_hidden_items",
    "verify_registered_scalar_tables",
    "verify_text_dictionary_pointers",
    "verify_text_message_bytes",
]
