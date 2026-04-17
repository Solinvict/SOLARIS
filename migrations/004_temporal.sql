-- SPDX-License-Identifier: MPL-2.0

ALTER TABLE claims ADD COLUMN valid_from TEXT;
ALTER TABLE claims ADD COLUMN valid_until TEXT;
ALTER TABLE claims ADD COLUMN superseded_at TEXT;
ALTER TABLE claims ADD COLUMN disputed_at TEXT;
ALTER TABLE claims ADD COLUMN last_reinforced_at TEXT;

ALTER TABLE relations ADD COLUMN valid_from TEXT;
ALTER TABLE relations ADD COLUMN valid_until TEXT;
ALTER TABLE relations ADD COLUMN superseded_at TEXT;
ALTER TABLE relations ADD COLUMN disputed_at TEXT;
ALTER TABLE relations ADD COLUMN last_reinforced_at TEXT;
