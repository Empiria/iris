# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

from ._anvil_designer import StaffSpikeTemplate


class StaffSpike(StaffSpikeTemplate):
    def __init__(self, **properties):
        self.init_components(**properties)
