from typing import Any, Dict, List, Optional, Union
from unittest.mock import MagicMock
import uuid

class FakeRequestBuilder:
    def __init__(self, table_name: str, data_store: Dict[str, List[Dict]]):
        self.table_name = table_name
        self.data_store = data_store
        self._filters = []
        self._data = None
        self._order = None
        self._limit = None

    def select(self, columns: str = "*"):
        return self

    def eq(self, column: str, value: Any):
        self._filters.append((column, value))
        return self
    
    def is_(self, column: str, value: Any):
        # Handle is_('processed', 'null') -> processed is None
        if value == 'null':
            value = None
        self._filters.append((column, value))
        return self

    def order(self, column: str, desc: bool = False):
        self._order = (column, desc)
        return self

    def limit(self, count: int):
        self._limit = count
        return self

    def insert(self, data: Union[Dict[str, Any], List[Dict[str, Any]]]):
        if isinstance(data, dict):
            data = [data]
        self._data = data
        return self

    def update(self, data: Dict[str, Any]):
        self._data = data
        return self
    
    def delete(self):
        self._data = "DELETE"
        return self

    def single(self):
        self._limit = 1
        self._single = True
        return self

    def execute(self):
        # Ensure table exists
        if self.table_name not in self.data_store:
            self.data_store[self.table_name] = []
            
        rows = self.data_store[self.table_name]
        
        # Identify matching rows based on filters
        # Note: This logic logic applies filters to ALL operations (Select, Update, Delete)
        # This mimics Supabase behavior where .eq() filters the target rows.
        
        # Helper to check if row matches filters
        def matches(row):
            for col, val in self._filters:
                if row.get(col) != val:
                    return False
            return True

        # Apply Insert
        if isinstance(self._data, list): # Insert
            inserted_rows = []
            for item in self._data:
                new_item = item.copy()
                # Auto-generate ID if missing
                if 'id' not in new_item:
                    new_item['id'] = str(uuid.uuid4())
                
                self.data_store[self.table_name].append(new_item)
                inserted_rows.append(new_item)
            
            # Return inserted
            return MagicMock(data=inserted_rows)

        # Apply Update
        if isinstance(self._data, dict):
            updated_rows = []
            for row in rows:
                if matches(row):
                    row.update(self._data)
                    updated_rows.append(row)
            return MagicMock(data=updated_rows)
            
        # Apply Delete
        if self._data == "DELETE":
            # Keep rows that DO NOT match
            remaining = [row for row in rows if not matches(row)]
            self.data_store[self.table_name] = remaining
            return MagicMock(data=[])

        # Select results
        filtered = [row for row in rows if matches(row)]
        
        if self._order:
            col, desc = self._order
            # Handle missing keys safely
            filtered.sort(key=lambda x: x.get(col, ""), reverse=desc)
            
        if self._limit:
            filtered = filtered[:self._limit]
            
        data = filtered
        if getattr(self, '_single', False):
            if filtered:
                data = filtered[0]
            else:
                data = None

        return MagicMock(data=data)

class FakeSupabaseClient:
    def __init__(self):
        self.data_store: Dict[str, List[Dict]] = {}

    def table(self, table_name: str):
        return FakeRequestBuilder(table_name, self.data_store)
