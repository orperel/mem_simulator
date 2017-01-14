from math import ceil
from math import log2

from mem_ifc import MemoryInterface


class L1Cache(MemoryInterface):
    """
        The Level 1 cache of the system.
        -   Can be connected directly to Main Memory, or to a Level 2 cache.
        -   Cache type: Direct-mapped, Write-back, Write-allocate.
        -   Uses 24 bits for address, 32 bit for data (both configurable).
        -   Initializes to 0 for all cells in beginning of each session.

        Assumption:
        -   Block size is a power of 2, between 4-128 bytes.
        -   Addresses are aligned to 4, no non aligned bytes may be accessed.
        -   When data does not fit entirely into the bus, assume each additional traversal on the bus takes 1 cc.
    """

    # L1 Cache parameters defined here
    CACHE_SIZE_IN_BYTES = 4 * 1024  # Mem capacity is 4K
    MEM_BUS_WIDTH = 32              # Bus width between L1 to previous, CPU level, in bits
    MEM_HIT_TIME = 1                # In clock cycles
    MEM_BUS_ACCESS_TIME = 1         # Any additional transfer on bus after accessing for first entry
    ADDRESS_BITS = 24               # Amount of bits allocated for addresses space in cache

    # L1 Cache contents, initialized to 0 until data is accessed
    data_mem = [0] * CACHE_SIZE_IN_BYTES
    tag_mem = []

    # Block size for L1 Cache
    block_size = -1

    # Number of bits allocated for each address component
    offset_bits = 0
    index_bits = 0
    tag_bits = 0

    # Tag memory table keeps track of the cached block lines, by storing a triplet of "tag"-"dirty bit"-"valid bit".
    # Implementation wise, we compress all 3 into a single variable for each block.
    # These indices help masking the dirty and valid bits out of the compressed representation of the triplet,
    # and are initialized according to the tag size.
    dirty_bit_index = 0x0
    valid_bit_index = 0x0

    # Masks for fetching components of the address, or tag memory state
    # We create once and reuse
    tag_mask = 0x0
    index_mask = 0x0
    offset_mask = 0x0
    tag_mem_mask = 0x0  # This version of the mask is not shifted since we store less bits for tag table
    dirty_mask = 0x0
    valid_mask = 0x0

    @staticmethod
    def create_mask(length: int, shift: int) -> int:
        """
        Creates a 32 bit mask of "length" bits of on. The mask is shifted "shift" amount of bits to the left.
        I.e: createMask(3,4) -> 00000000 00000000 00000000 01110000
        :param length: Amount on "on" bits
        :param shift: Amount of shifting the "on" bits to the left
        :return: Bit mask of "length" bits, shifted "shift" amount.
        """
        mask = 0x0
        for c in range(0, length-1):
            mask |= 0x1
            mask <<= 1

        mask |= 0x1  # Apply last bit
        mask <<= shift  # Shift amount of bits required

        return mask

    def __init__(self, next_mem_arg: MemoryInterface, block_size: int):
        """
        C'tor for L1 Cache object, initialized to 0 for each mem cell in the beginning of each simulation.
        :param next_mem_arg: A pointer to the next memory level in the hierarchy (L2 cache or Main memory)
        :param block_size: Block size for this level of cache (atomic actions operate on this amount of bytes).
        """
        super(L1Cache, self).__init__(next_mem_arg)  # Call super constructor with next level of hierarchy
        self.block_size = block_size

        num_of_blocks = int(self.CACHE_SIZE_IN_BYTES / block_size)

        # Assumptions:
        # - Dirty & Valid bit are not included within the address bits.
        # - All addresses are expected to be aligned to 4, and CPU is not expected to fetch non-aligned addresses.
        #   The offset bits include the 2 LSB of alignment bits.
        #   This can easily be changed by subtracting 2 from the number of offset bits
        self.offset_bits = int(log2(block_size))  # Includes 2 LSB of alignment bits
        self.index_bits = int(log2(num_of_blocks))
        self.tag_bits = self.ADDRESS_BITS - self.offset_bits - self.index_bits

        # Create the masks used to differentiate the 24 bit address components:
        self.offset_mask = self.create_mask(self.offset_bits, 0)
        self.index_mask = self.create_mask(self.index_bits, self.offset_bits)
        self.tag_mask = self.create_mask(self.tag_bits, self.offset_bits + self.index_bits)
        self.tag_mem_mask = self.create_mask(self.tag_bits, 0)  # For tag memory table

        # Dirty and valid bits are compressed with tag bits in the same cell in the tag memory, so their index
        # is following right after the number of tag bits used (address is 24 bit, less then 32 bit int of python)
        self.dirty_bit_index = self.tag_bits
        self.valid_bit_index = self.tag_bits + 1

        # Dirty and valid masks compose of 1 bit, and are the next MSB after the tag bits in the tag mem cells
        self.dirty_mask = self.create_mask(1, self.dirty_bit_index)
        self.valid_mask = self.create_mask(1, self.valid_bit_index)

        # Initialize the tag memory according to the number of blocks in cache
        self.tag_mem = [0] * num_of_blocks

    def address_to_offset(self, address: int) -> int:
        """
        Return the offset of the address within the block
        :param address: Address input
        :return: Offset bits only, as LSB (meaning: the index of the address within the block)
        """
        offset = (address & self.offset_bits)
        return offset

    def address_to_block_num(self, address: int) -> int:
        """
        Return the index of the address
        :param address: Address input
        :return: Index bits, shifted to LSB (meaning: the block number which belongs to this address for Direct Mapped)
        """
        index = (address & self.index_mask) >> self.offset_bits
        return index

    def address_to_tag(self, address: int) -> int:
        """
        Return the tag of the address
        :param address: Address input
        :return: Tag bits, shifted to LSB.
        """
        address_tag = (address & self.tag_mask) >> (self.offset_bits + self.index_bits)
        return address_tag

    def address_from_tag_index(self, tag: int, index: int) -> int:
        """
        Construct address from tag and index bits (offset is assumed as 0)
        :param tag: tag bits of the address (expected to use correct amount of tag bits)
        :param index: index bits of the address (expected to use correct amount of index bits)
        :return: Fully reconstructed address composed of "ADDRESS_BITS" amount of bits.
        """
        tag_shifted = tag << (self.offset_bits + self.index_bits)
        index_shifted = index << self.offset_bits
        address = tag_shifted | index_shifted
        return address

    def transfer_cycles(self, data_size: int) -> int:
        """
        Returns the amount of cycles needed to read / write the data_size given to the L1 cache.
        (this is the amount of times it takes to pass data on the bus between L1 cache and the previous level
        in the hierarchy).
        :param data_size: The amount of data passed on the bus, excluding address size
        :return: Amount of cycles taken to pass the data on the bus
        """
        return self.MEM_HIT_TIME +\
               (ceil(data_size / self.MEM_BUS_WIDTH) - 1) * self.MEM_BUS_ACCESS_TIME

    def is_address_present(self, address: int) -> bool:
        """
        Query if the data in the given address is present in the current memory level.
        :param address: Address to query if the data is contained in the current memory level
        :return: True if the memory of this address resides in the current mem level, false is not.
                 This is determined by the valid bit and if the tag in memory matches tag of given address.
        """

        # Fetch the index bits to choose the block tag data from the tag memory
        index = self.address_to_block_num(address)
        cached_tag_mem = self.tag_mem[index]

        # Check the valid bit, and compare tags
        address_tag = self.address_to_tag(address)
        cache_tag = cached_tag_mem & self.tag_mem_mask
        is_valid = bool((cached_tag_mem & self.valid_mask) >> self.valid_bit_index)

        return is_valid and (address_tag == cache_tag)

    def get_block_size(self) -> int:
        """
        :return: The block size in bytes for L1 cache
        """
        return self.block_size

    def flush_if_needed(self, address: int) -> int:
        """
        This callback is triggered after a new block is loaded from the next mem level,
        and it may conflict with an older block currently residing in the cache (identical block numbers).
        This method checks if the old block is dirty and valid,
        and if needed it will take care to flush it to the next level, according to the cache logic.
        :param address: Address of new block we wish to write, 4 byte aligned.
                        This address's tag may conflict with an older block with similar block number and a
                        different tag, in which case we flush the old block.
        :return: (clock cycles elapsed to flush old block as int -  0 if no flush have occurred)
        """

        # Fetch the index bits to choose the block tag data from the tag memory
        index = self.address_to_block_num(address)
        cached_tag_mem = self.tag_mem[index]

        # Check the valid & dirty bits
        is_valid = (cached_tag_mem & self.valid_mask) >> self.valid_bit_index
        is_dirty = (cached_tag_mem & self.dirty_mask) >> self.dirty_bit_index

        cycles_elapsed = 0

        # Only flush to next level if block is valid and content is dirty
        if is_valid and is_dirty:

            # First read the old block data we should flush (ignore cycles_elapsed, this is not a read operation
            # that sends data over the bus so no cycles should elapse).
            block_start_address = index * self.block_size
            data = self.read(block_start_address, self.block_size)[0]

            # Reconstruct the flushed block address by using the cached tag value and index bits
            tag = cached_tag_mem & self.tag_mem_mask  # Filter out valid, dirty bits
            flushed_address = self.address_from_tag_index(tag, index)
            cycles_elapsed = self.next_mem.store(flushed_address, self.block_size, data)  # Flush block to next level
            self.tag_mem[index] &= ~self.dirty_mask  # Turn dirty bit off

        return cycles_elapsed

    def write(self, address: int, mark_dirty: bool, data_size: int, data=[]) -> int:
        """
        Save the data to the given address.
        Data will be marked as "valid" and possibly "dirty", according to write-back policy.
        Handling dirty data that already occupies the cache is not the concern of this method,
        we assume that all data that should be committed have already been taken care of.
        This method may update only part of the block, or an entire block, according to data_size given.
        :param address: Address to write to, 4 byte aligned
        :param mark_dirty: When true, the written block will be marked as dirty. False when not.
        :param data_size: Data size to write to memory, in amount of bytes
        :param data: Data to be saved, as a list of bytes, little endian format expected (will be saved as is)
        :return: (clock cycles elapsed as int - this is the amount of cycles expected to take to transfer the
                  writen data on the bus from the CPU to L1 Cache)
        """

        # Fetch the index bits to choose the block from the data memory
        block_num = self.address_to_block_num(address)
        offset = self.address_to_offset(address)  # Offset of address within the block
        start = block_num * self.block_size + offset  # Note: We read the amount of bytes equal to data_size
        end = start + data_size

        # Copy data to data memory
        for new_data_cursor, mem_cursor in enumerate(range(start, end)):
            self.data_mem[mem_cursor] = data[new_data_cursor]

        # Update tag memory, turn both valid and (possibly) dirty bits on
        tag = self.address_to_tag(address)
        tag_mem_entry = tag | self.valid_mask

        if mark_dirty:
            tag_mem_entry |= self.dirty_mask

        self.tag_mem[block_num] = tag_mem_entry

        elapsed_time = self.transfer_cycles(data_size)

        return elapsed_time

    def read(self, address: int, data_size: int) -> (list, int):
        """
        Perform read operation from the memory, using the memory's inner logic.
        This method assumes the data is stored in the cache, and is valid.
        :param address: Address to read from, 4 byte aligned
        :param data_size: Amount of data in bytes to read from L1 cache memory and return to previous level.
                          Note this is not necessarily the L1Cache block_size: the previous level may request less bytes
                          to transfer on the bus.
        :return: (data read as list of bytes, clock cycles elapsed as int to pass this data to previous mem level)
        """

        # Fetch the index bits to choose the block from the data memory
        block_num = self.address_to_block_num(address)
        offset = self.address_to_offset(address)  # Offset of address within the block
        start = block_num * self.block_size + offset  # Note: We read the amount of bytes equal to data_size
        end = start + data_size

        # Read a whole block
        data_read = self.data_mem[start:end]

        # L1 cache only knows how to read amount of bytes according to L1 Cache block_size, but
        # the CPU may request "less bytes than L1.BlockSize"
        # Therefore we calculate the expected transfer time according to the amount of data sent on the bus.
        elapsed_time = self.transfer_cycles(data_size)

        return data_read, elapsed_time

    def dump_memory(self, *file_names):
        """ Dumps the contents of memory hierarchy to the file names given as argument.
            Each level may use one or two files, and pass the rest of the list to the next level.
            For example: (l1.txt, l2way0.txt, l2way1.txt, memout.txt), L1 will use l1.txt and pass
            (l2way0.txt, l2way1.txt, memout.txt) to L2 cache, which passes (memout.txt) to MainMemory.
            The format used in each file is byte-per-line, no headers or footers."""
        file_name = file_names[0]
        self.dump_output_file(file_name, self.data_mem)
        self.next_mem.dump_memory(*file_names[1:])

    def print_mem(self, limit=-1):
        """Prints the contents of the L1 cache tag / data to the console, for debugging and logging purposes.
           limit args allows to print only first "limit" lines to avoid bloating the console."""
        cursor = 0
        print("L1 cache - tag memory:")
        for entry in self.tag_mem:
            if cursor % 4 == 0:
                print('\n0x' + str(cursor).zfill(6) + ' ', end="")
            print(hex(entry)[2:] + ' ', end="")
            cursor += 1
            if cursor == limit:
                break

        cursor = 0
        print("L1 cache - data memory:")
        for entry in self.data_mem:
            if cursor % 4 == 0:
                print('\n0x' + str(cursor).zfill(6) + ' ', end="")
            print(hex(entry)[2:] + ' ', end="")
            cursor += 1
            if cursor == limit:
                break

        # Print the next level in hierarchy
        self.next_mem.print_mem(limit)

        return
