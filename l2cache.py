from mem_ifc import MemoryInterface
from l1cache import L1Cache
from math import log2, ceil

class L2Cache(MemoryInterface):
    # L2 Cache parameters defined here
    CACHE_SIZE_IN_BYTES = 32 * 1024  # Mem capacity is 32K for each way
    NUM_OF_WAYS = 2  # Number of ways
    MEM_BUS_WIDTH = 256  # In bits
    MEM_HIT_TIME = 4  # In clock cycles
    MEM_BUS_ACCESS_TIME = 1  # Any additional transfer on bus after accessing for first entry

    def __init__(self, next_mem_arg: MemoryInterface, block_size: int):
        """
        C'tor for L2 Cache object, initialized to 0 for each mem cell in the beginning of each simulation.
        :param next_mem_arg: A pointer to the next memory level in the hierarchy (L2 cache or Main memory)
        :param block_size: Block size for this level of cache (atomic actions operate on this amount of bytes).
        """
        super(L2Cache, self).__init__(next_mem_arg)  # Call super constructor with next level of hierarchy

        self.block_size = block_size
        num_of_lines = int(self.CACHE_SIZE_IN_BYTES / (self.NUM_OF_WAYS*block_size))

        self.data_mem = [[[0 for i in range(block_size)] for j in range(self.NUM_OF_WAYS)] for k in range(num_of_lines)]
        self.tag_mem = [[0 for i in range(self.NUM_OF_WAYS)] for j in range(num_of_lines)]
        self.lru_mem = [0 for i in range(num_of_lines)]

        self.offset_bits = int(log2(block_size))  # Includes 2 LSB of alignment bits
        self.index_bits = int(log2(num_of_lines))
        self.tag_bits = L1Cache.ADDRESS_BITS - self.index_bits - self.offset_bits

        # Create the masks used to differentiate the 24 bit address components:
        self.offset_mask = L1Cache.create_mask(self.offset_bits, 0)
        self.index_mask = L1Cache.create_mask(self.index_bits, self.offset_bits)
        self.tag_mask = L1Cache.create_mask(self.tag_bits, self.offset_bits + self.index_bits)
        self.tag_mem_mask = L1Cache.create_mask(self.tag_bits, 0)  # For tag memory table

        # Dirty and valid bits are compressed with tag bits in the same cell in the tag memory, so their index
        # is following right after the number of tag bits used (address is 24 bit, less then 32 bit int of python)
        self.dirty_bit_index = self.tag_bits 
        self.valid_bit_index = self.tag_bits + 1

        # Dirty and valid masks compose of 1 bit, and are the next MSB after the tag bits in the tag mem cells
        self.dirty_mask = L1Cache.create_mask(1, self.dirty_bit_index)
        self.valid_mask = L1Cache.create_mask(1, self.valid_bit_index)

    def get_block_size(self) -> int:
        """
        :return: The block size in bytes for L2 Cache
        """
        return self.block_size

    def apply_mask(self, num: int, mask: int, shift_right: int) -> int:
        return (num & mask) >> shift_right

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

    def address_present_in_way(self, address: int) -> int:
        index = self.apply_mask(address, self.index_mask, self.offset_bits)
        address_tag = self.apply_mask(address, self.tag_mask, self.offset_bits + self.index_bits)

        cached_tag_mem = self.tag_mem[index]    # Tuple
        present_in_way = -1
        for i in range(self.NUM_OF_WAYS):
            valid_bit = self.apply_mask(cached_tag_mem[i], self.valid_mask, self.valid_bit_index)
            if valid_bit:
                way_tag = self.apply_mask(cached_tag_mem[i], self.tag_mem_mask, 0)
                if address_tag == way_tag:
                    present_in_way = i
                    break
        
        return present_in_way

    def is_address_present(self, address: int) -> bool:
        """
        Query if the data in the given address is present in the current memory level
        :param address: Address to query if the data is contained in the current memory level
        :return: True if the memory of this address resides in the current mem level, false is not.
        """
        return (self.address_present_in_way(address) != -1)

    def transfer_cycles(self, data_size: int) -> int:
        """
        Returns the amount of cycles needed to read / write the data_size given to the L2 cache.
        (this is the amount of times it takes to pass data on the bus between L2 cache and the previous level
        in the hierarchy).
        :param data_size: The amount of data passed on the bus, excluding address size
        :return: Amount of cycles taken to pass the data on the bus
        """
        return self.MEM_HIT_TIME +\
               (ceil(8*data_size / self.MEM_BUS_WIDTH) - 1) * self.MEM_BUS_ACCESS_TIME

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
        index = self.apply_mask(address, self.index_mask, self.offset_bits)
        cached_tag_mem = self.tag_mem[index][self.lru_mem[index]]

        # Check the valid & dirty bits
        is_valid = self.apply_mask(cached_tag_mem, self.valid_mask, self.valid_bit_index)
        is_dirty = self.apply_mask(cached_tag_mem, self.dirty_mask, self.dirty_bit_index)

        cycles_elapsed = 0
        
        # Only flush to next level if block is valid and content is dirty
        if is_valid and is_dirty:
            # Reconstruct the flushed block address by using the cached tag value and index bits
            tag = self.apply_mask(cached_tag_mem, self.tag_mem_mask, 0) # Filter out valid, dirty bits
            flushed_address = self.address_from_tag_index(tag, index)
            
            # First read the old block data we should flush (ignore cycles_elapsed, this is not a read operation
            # that sends data over the bus so no cycles should elapse).
            data = self.read(flushed_address, self.block_size)[0]
            self.lru_mem[index] = 1 - self.lru_mem[index]   # We don't want to change here the LRU

            # Flush block to next level
            cycles_elapsed = self.next_mem.store(flushed_address, self.block_size, data)

            # Turn dirty bit off
            self.tag_mem[index][self.lru_mem[index]] &= ~self.dirty_mask

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
                  writen data on the bus from the L1 cache to the L2 cache)
        """
        # Fetch the index bits to choose the block from the data memory
        index = self.apply_mask(address, self.index_mask, self.offset_bits)
        if mark_dirty:
            way = self.address_present_in_way(address)
        else:
            way = self.lru_mem[index]
        start = self.apply_mask(address, self.offset_mask, 0)   # Offset of address within the block
        end = start + data_size
        
        # Copy data to data memory
        for new_data_cursor, mem_cursor in enumerate(range(start, end)):
            self.data_mem[index][way][mem_cursor] = data[new_data_cursor]

        # Update tag memory, turn both valid and (possibly) dirty bits on
        tag = self.apply_mask(address, self.tag_mask, self.offset_bits + self.index_bits)
        tag_mem_entry = tag | self.valid_mask
        if mark_dirty:
            tag_mem_entry |= self.dirty_mask
        self.tag_mem[index][way] = tag_mem_entry

        # Update LRU - assuming there are only 2 ways, for more ways needed to implement something more complex
        if self.lru_mem[index] == way:
            self.lru_mem[index] = 1 - way

        elapsed_time = self.transfer_cycles(data_size)

        return elapsed_time

    def read(self, address: int, data_size: int) -> (list, int):
        """
        Perform read operation from the memory, using the memory's inner logic.
        This method assumes the data is stored in the cache, and is valid.
        :param address: Address to read from, 4 byte aligned
        :param data_size: Amount of data in bytes to read from current memory level and return to previous level.
                          Note this is not necessarily the block size: the previous level may request less bytes
                          to transfer on the bus.
        :return: (data read as list of bytes, clock cycles elapsed as int to pass this data to previous mem level)
        """
         # Fetch the index bits to choose the block from the data memory
        index = self.apply_mask(address, self.index_mask, self.offset_bits)
        way = self.address_present_in_way(address)
        start = self.apply_mask(address, self.offset_mask, 0)   # Offset of address within the block
        end = start + data_size

        # Read a whole data
        data_read = self.data_mem[index][way][start:end]

        # Update LRU - assuming there are only 2 ways, for more ways needed to implement something more complex
        if self.lru_mem[index] == way:
            self.lru_mem[index] = 1 - way

        # L2 cache only knows how to read amount of bytes according to L2 Cache block_size, but
        # L1 may request "less bytes than L2.BlockSize"
        # Therefore we calculate the expected transfer time according to the amount of data sent on the bus.
        elapsed_time = self.transfer_cycles(data_size)

        return data_read, elapsed_time

    def mem_table_to_list(self, way: int) -> list:
        mem_list = []
        for i in range(len(self.data_mem)):
            mem_list.extend(self.data_mem[i][way])
        return mem_list
        
    def dump_memory(self, *file_names):
        """ Dumps the contents of memory hierarchy to the file names given as argument.
            Each level may use one or two files, and pass the rest of the list to the next level.
            For example: (l1.txt, l2way0.txt, l2way1.txt, memout.txt), L1 will use l1.txt and pass
            (l2way0.txt, l2way1.txt, memout.txt) to L2 cache, which passes (memout.txt) to MainMemory.
            The format used in each file is byte-per-line, no headers or footers."""
        way0_file_name = file_names[0]
        way1_file_name = file_names[1]
        self.dump_output_file(way0_file_name, self.mem_table_to_list(0))
        self.dump_output_file(way1_file_name, self.mem_table_to_list(1))
        self.next_mem.dump_memory(*file_names[2:])

    def print_mem(self, limit=-1):
        self.next_mem.print_mem(limit)
        # TODO: Implement..?
        return
