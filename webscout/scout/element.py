"""
Scout Element Module - Advanced HTML Element Representation
"""

import re
from typing import Any, Dict, List, Optional, Union


class NavigableString(str):
    """
    A string that knows its place in the document tree.
    Mimics BeautifulSoup's NavigableString for better compatibility.
    """
    def __new__(cls, text: str):
        """
        Create a new NavigableString instance.

        Args:
            text (str): String content
        """
        return str.__new__(cls, text)

    def __init__(self, text: str):
        """
        Initialize a navigable string.

        Args:
            text (str): String content
        """
        self.parent = None

    def __repr__(self):
        """String representation."""
        return f"NavigableString({super().__repr__()})"

    def __add__(self, other):
        """
        Allow concatenation of NavigableString with other strings.

        Args:
            other (str): String to concatenate

        Returns:
            str: Concatenated string
        """
        return str(self) + str(other)

    def strip(self, chars=None):
        """
        Strip whitespace or specified characters.

        Args:
            chars (str, optional): Characters to strip

        Returns:
            str: Stripped string
        """
        return NavigableString(super().strip(chars))

class Tag:
    """
    Represents an HTML tag with advanced traversal and manipulation capabilities.
    Enhanced to closely mimic BeautifulSoup's Tag class.
    """
    def __init__(self, name: str, attrs: Dict[str, str] = None):
        """
        Initialize a Tag with name and attributes.

        Args:
            name (str): Tag name
            attrs (dict, optional): Tag attributes
        """
        self.name = name
        self.attrs = attrs or {}
        self.contents = []
        self.parent = None
        self.string = None  # For single string content

    def __str__(self):
        """String representation of the tag."""
        return self.decode_contents()

    def __repr__(self):
        """Detailed representation of the tag."""
        return f"<{self.name} {self.attrs}>"

    def __call__(self, *args, **kwargs):
        """
        Allows calling find_all directly on the tag.
        Mimics BeautifulSoup's behavior.
        """
        return self.find_all(*args, **kwargs)

    def __contains__(self, item):
        """
        Check if an item is in the tag's contents.

        Args:
            item: Item to search for

        Returns:
            bool: True if item is in contents, False otherwise
        """
        return item in self.contents

    def __getitem__(self, key):
        """
        Get an attribute value using dictionary-like access.

        Args:
            key (str): Attribute name

        Returns:
            Any: Attribute value
        """
        return self.attrs[key]

    def __iter__(self):
        """
        Iterate through tag's contents.

        Returns:
            Iterator: Contents of the tag
        """
        return iter(self.contents)

    def __eq__(self, other):
        """
        Compare tags based on name and attributes.

        Args:
            other (Tag): Tag to compare

        Returns:
            bool: True if tags are equivalent
        """
        if not isinstance(other, Tag):
            return False
        return (
            self.name == other.name and
            self.attrs == other.attrs and
            str(self) == str(other)
        )

    def __hash__(self):
        """
        Generate a hash for the tag.

        Returns:
            int: Hash value
        """
        return hash((self.name, frozenset(self.attrs.items()), str(self)))

    def find(self, name=None, attrs={}, recursive=True, text=None, limit=None, class_=None, **kwargs) -> Optional['Tag']:
        """
        Find the first matching child element.
        Enhanced with more flexible matching.

        Args:
            name (str, optional): Tag name to search for
            attrs (dict, optional): Attributes to match
            recursive (bool, optional): Search recursively
            text (str, optional): Text content to match

        Returns:
            Tag or None: First matching element
        """
        # Merge class_ with attrs['class'] if both are present
        attrs = dict(attrs) if attrs else {}
        if class_ is not None:
            if 'class' in attrs:
                # Merge both
                if isinstance(attrs['class'], list):
                    class_list = attrs['class']
                else:
                    class_list = [cls.strip() for cls in re.split(r'[ ,]+', str(attrs['class'])) if cls.strip()]
                if isinstance(class_, list):
                    class_list += class_
                else:
                    class_list += [cls.strip() for cls in re.split(r'[ ,]+', str(class_)) if cls.strip()]
                attrs['class'] = class_list
            else:
                attrs['class'] = class_
        results = self.find_all(name, attrs, recursive, text, limit=1, **kwargs)
        return results[0] if results else None

    def find_all(self, name=None, attrs={}, recursive=True, text=None, limit=None, class_=None, **kwargs) -> List['Tag']:
        """
        Find all matching child elements.
        Enhanced with more flexible matching and BeautifulSoup-like features.

        Args:
            name (str, optional): Tag name to search for
            attrs (dict, optional): Attributes to match
            recursive (bool, optional): Search recursively
            text (str, optional): Text content to match
            limit (int, optional): Maximum number of results

        Returns:
            List[Tag]: List of matching elements
        """
        results = []

        def _match(tag):
            # Check tag name with case-insensitive and regex support
            if name:
                if isinstance(name, str):
                    if tag.name.lower() != name.lower():
                        return False
                elif isinstance(name, re.Pattern):
                    if not name.search(tag.name):
                        return False

            # Check attributes with more flexible matching
            for k, v in attrs.items():
                if k == 'class':
                    tag_classes = tag.get('class', [])
                    # Support multiple classes separated by space or comma
                    if isinstance(v, str):
                        v_classes = [cls.strip() for cls in re.split(r'[ ,]+', v) if cls.strip()]
                        if not all(cls in tag_classes for cls in v_classes):
                            return False
                    elif isinstance(v, list):
                        if not all(cls in tag_classes for cls in v):
                            return False
                    else:
                        return False
                elif k == 'id':
                    if tag.get('id') != v:
                        return False
                else:
                    # Regex or exact match for other attributes
                    tag_attr = tag.attrs.get(k)
                    if v is True:
                        if tag_attr is None:
                            return False
                    elif isinstance(v, re.Pattern):
                        if tag_attr is None or not v.search(str(tag_attr)):
                            return False
                    elif tag_attr != v:
                        return False

            # Check text content
            if text:
                tag_text = tag.get_text(strip=True)
                if isinstance(text, str) and text.lower() not in tag_text.lower():
                    return False
                elif isinstance(text, re.Pattern) and not text.search(tag_text):
                    return False

            return True

        def _search(element):
            if _match(element):
                results.append(element)
                if limit and len(results) == limit:
                    return

            if recursive:
                for child in element.contents:
                    if isinstance(child, Tag):
                        _search(child)

        _search(self)
        return results

    def select(self, selector: str) -> List['Tag']:
        """
        Select elements using CSS selector.
        Enhanced to support more complex selectors including:
        - Tag selectors: 'p', 'div'
        - Class selectors: '.class', 'p.class'
        - ID selectors: '#id', 'div#id'
        - Attribute selectors: '[attr]', '[attr=value]'
        - Descendant selectors: 'div p'
        - Child selectors: 'div > p'
        - Multiple classes: '.class1.class2'

        Args:
            selector (str): CSS selector string

        Returns:
            List[Tag]: List of matching elements
        """
        results = []
        
        def _parse_simple_selector(simple_sel: str) -> dict:
            """Parse a simple selector like 'p.class#id[attr=value]' into components."""
            components = {
                'tag': None,
                'id': None,
                'classes': [],
                'attrs': {}
            }
            
            # Extract tag name (at the start)
            tag_match = re.match(r'^([a-zA-Z][\w-]*)', simple_sel)
            if tag_match:
                components['tag'] = tag_match.group(1)
                simple_sel = simple_sel[len(tag_match.group(1)):]
            
            # Extract ID
            id_matches = re.findall(r'#([\w-]+)', simple_sel)
            if id_matches:
                components['id'] = id_matches[0]
            
            # Extract classes
            class_matches = re.findall(r'\.([\w-]+)', simple_sel)
            components['classes'] = class_matches
            
            # Extract attributes
            attr_matches = re.findall(r'\[([^\]]+)\]', simple_sel)
            for attr_expr in attr_matches:
                if '=' in attr_expr:
                    attr_name, attr_value = attr_expr.split('=', 1)
                    components['attrs'][attr_name.strip()] = attr_value.strip('\'"')
                else:
                    components['attrs'][attr_expr.strip()] = None
            
            return components
        
        def _match_simple_selector(tag: 'Tag', components: dict) -> bool:
            """Check if a tag matches the parsed selector components."""
            # Check tag name
            if components['tag'] and tag.name != components['tag']:
                return False
            
            # Check ID
            if components['id'] and tag.get('id') != components['id']:
                return False
            
            # Check classes
            tag_classes = tag.get('class', '')
            if isinstance(tag_classes, str):
                tag_classes = tag_classes.split()
            elif not isinstance(tag_classes, list):
                tag_classes = [str(tag_classes)] if tag_classes else []
            
            for cls in components['classes']:
                if cls not in tag_classes:
                    return False
            
            # Check attributes
            for attr_name, attr_value in components['attrs'].items():
                if attr_value is None:
                    # Just check attribute exists
                    if attr_name not in tag.attrs:
                        return False
                else:
                    # Check attribute value
                    if tag.get(attr_name) != attr_value:
                        return False
            
            return True
        
        def _find_all_matching(element: 'Tag', components: dict) -> List['Tag']:
            """Recursively find all elements matching the selector components."""
            matches = []
            
            # Check current element
            if _match_simple_selector(element, components):
                matches.append(element)
            
            # Check children recursively
            for child in element.contents:
                if isinstance(child, Tag):
                    matches.extend(_find_all_matching(child, components))
            
            return matches
        
        # Handle combinators (descendant ' ' and child '>')
        if ' > ' in selector:
            # Child combinator
            parts = [p.strip() for p in selector.split(' > ')]
            return self._select_with_child_combinator(parts)
        elif ' ' in selector.strip():
            # Descendant combinator
            parts = [p.strip() for p in selector.split()]
            return self._select_with_descendant_combinator(parts)
        else:
            # Simple selector
            components = _parse_simple_selector(selector)
            return _find_all_matching(self, components)
    
    def _select_with_descendant_combinator(self, parts: List[str]) -> List['Tag']:
        """Handle descendant combinator (space)."""
        if not parts:
            return []
        
        if len(parts) == 1:
            components = self._parse_selector_components(parts[0])
            return self._find_all_matching_in_tree(self, components)
        
        # Find elements matching the first part
        first_components = self._parse_selector_components(parts[0])
        first_matches = self._find_all_matching_in_tree(self, first_components)
        
        # For each match, find descendants matching remaining parts
        results = []
        remaining_selector = ' '.join(parts[1:])
        for match in first_matches:
            descendants = match.select(remaining_selector)
            results.extend(descendants)
        
        return results
    
    def _select_with_child_combinator(self, parts: List[str]) -> List['Tag']:
        """Handle child combinator (>)."""
        if not parts:
            return []
        
        if len(parts) == 1:
            components = self._parse_selector_components(parts[0])
            return self._find_all_matching_in_tree(self, components)
        
        # Find elements matching the first part
        first_components = self._parse_selector_components(parts[0])
        first_matches = self._find_all_matching_in_tree(self, first_components)
        
        # For each match, find direct children matching the next part
        if len(parts) == 2:
            # Last part, just check direct children
            next_components = self._parse_selector_components(parts[1])
            results = []
            for match in first_matches:
                for child in match.contents:
                    if isinstance(child, Tag) and self._match_selector_components(child, next_components):
                        results.append(child)
            return results
        else:
            # More parts, need to continue recursively
            results = []
            next_components = self._parse_selector_components(parts[1])
            remaining_parts = parts[2:]
            for match in first_matches:
                for child in match.contents:
                    if isinstance(child, Tag) and self._match_selector_components(child, next_components):
                        # Continue with remaining parts
                        remaining_selector = ' > '.join(remaining_parts)
                        descendants = child.select(remaining_selector)
                        results.extend(descendants)
            return results
    
    def _parse_selector_components(self, simple_sel: str) -> dict:
        """Parse a simple selector like 'p.class#id[attr=value]' into components."""
        components = {
            'tag': None,
            'id': None,
            'classes': [],
            'attrs': {}
        }
        
        # Extract tag name (at the start)
        tag_match = re.match(r'^([a-zA-Z][\w-]*)', simple_sel)
        if tag_match:
            components['tag'] = tag_match.group(1)
            simple_sel = simple_sel[len(tag_match.group(1)):]
        
        # Extract ID
        id_matches = re.findall(r'#([\w-]+)', simple_sel)
        if id_matches:
            components['id'] = id_matches[0]
        
        # Extract classes
        class_matches = re.findall(r'\.([\w-]+)', simple_sel)
        components['classes'] = class_matches
        
        # Extract attributes
        attr_matches = re.findall(r'\[([^\]]+)\]', simple_sel)
        for attr_expr in attr_matches:
            if '=' in attr_expr:
                attr_name, attr_value = attr_expr.split('=', 1)
                components['attrs'][attr_name.strip()] = attr_value.strip('\'"')
            else:
                components['attrs'][attr_expr.strip()] = None
        
        return components
    
    def _match_selector_components(self, tag: 'Tag', components: dict) -> bool:
        """Check if a tag matches the parsed selector components."""
        # Check tag name
        if components['tag'] and tag.name != components['tag']:
            return False
        
        # Check ID
        if components['id'] and tag.get('id') != components['id']:
            return False
        
        # Check classes
        tag_classes = tag.get('class', '')
        if isinstance(tag_classes, str):
            tag_classes = tag_classes.split()
        elif not isinstance(tag_classes, list):
            tag_classes = [str(tag_classes)] if tag_classes else []
        
        for cls in components['classes']:
            if cls not in tag_classes:
                return False
        
        # Check attributes
        for attr_name, attr_value in components['attrs'].items():
            if attr_value is None:
                # Just check attribute exists
                if attr_name not in tag.attrs:
                    return False
            else:
                # Check attribute value
                if tag.get(attr_name) != attr_value:
                    return False
        
        return True
    
    def _find_all_matching_in_tree(self, element: 'Tag', components: dict) -> List['Tag']:
        """Recursively find all elements matching the selector components."""
        matches = []
        
        # Check current element
        if self._match_selector_components(element, components):
            matches.append(element)
        
        # Check children recursively
        for child in element.contents:
            if isinstance(child, Tag):
                matches.extend(self._find_all_matching_in_tree(child, components))
        
        return matches

    def select_one(self, selector: str) -> Optional['Tag']:
        """
        Select the first element matching the CSS selector.

        Args:
            selector (str): CSS selector string

        Returns:
            Tag or None: First matching element
        """
        results = self.select(selector)
        return results[0] if results else None

    def get_text(self, separator=' ', strip=False, types=None) -> str:
        """
        Extract text from the tag and its descendants.
        Enhanced to support more flexible text extraction.

        Args:
            separator (str, optional): Text separator
            strip (bool, optional): Strip whitespace
            types (list, optional): Types of content to extract

        Returns:
            str: Extracted text
        """
        texts = []
        for content in self.contents:
            # Support filtering by content type
            if types is None or type(content) in types:
                if isinstance(content, NavigableString):
                    texts.append(str(content))
                elif isinstance(content, Tag):
                    texts.append(content.get_text(separator, strip))

        text = separator.join(texts)
        text = re.sub(r'\n\n+', '\n', text) # Replace multiple newlines with single newlines
        return text.strip() if strip else text

    def find_text(self, pattern: Union[str, re.Pattern], **kwargs) -> Optional[str]:
        """
        Find the first text matching a pattern.

        Args:
            pattern (str or re.Pattern): Pattern to match
            **kwargs: Additional arguments for get_text()

        Returns:
            str or None: First matching text
        """
        text = self.get_text(**kwargs)

        if isinstance(pattern, str):
            return pattern if pattern in text else None
        elif isinstance(pattern, re.Pattern):
            match = pattern.search(text)
            return match.group(0) if match else None

    def replace_text(self, old: Union[str, re.Pattern], new: str, **kwargs) -> str:
        """
        Replace text matching a pattern.

        Args:
            old (str or re.Pattern): Pattern to replace
            new (str): Replacement text
            **kwargs: Additional arguments for get_text()

        Returns:
            str: Modified text
        """
        text = self.get_text(**kwargs)

        if isinstance(old, str):
            return text.replace(old, new)
        elif isinstance(old, re.Pattern):
            return old.sub(new, text)

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get an attribute value.

        Args:
            key (str): Attribute name
            default (Any, optional): Default value if attribute not found

        Returns:
            Any: Attribute value or default
        """
        return self.attrs.get(key, default)

    def decompose(self) -> None:
        """Remove the tag and its contents from the document."""
        if self.parent:
            self.parent.contents.remove(self)

    def extract(self) -> 'Tag':
        """
        Remove the tag from the document and return it.

        Returns:
            Tag: Extracted tag
        """
        self.decompose()
        return self

    def clear(self) -> None:
        """Remove all contents of the tag."""
        self.contents.clear()

    @property
    def string(self):
        """
        Get the string content of the tag.
        Returns the combined text of the tag's contents.
        """
        return self.get_text()

    @string.setter
    def string(self, value):
        """
        Set the string content of the tag.
        Clears existing contents and sets new string value.

        Args:
            value (str): New string content
        """
        self.clear()
        if value is not None:
            self.append(value)

    def append(self, new_child: Union['Tag', NavigableString, str]) -> None:
        """Append a new child to this tag with error handling."""
        if isinstance(new_child, str):
            new_child = NavigableString(new_child)
        if hasattr(new_child, 'parent'):
            new_child.parent = self
        self.contents.append(new_child)

    def extend(self, new_children: List[Union['Tag', NavigableString, str]]) -> None:
        """Extend the contents of this tag with a list of new children."""
        for child in new_children:
            self.append(child)

    def insert(self, index: int, new_child: Union['Tag', NavigableString, str]) -> None:
        """Insert a new child at the given index with error handling."""
        if isinstance(new_child, str):
            new_child = NavigableString(new_child)
        if hasattr(new_child, 'parent'):
            new_child.parent = self
        self.contents.insert(index, new_child)

    def replace_with(self, new_tag: 'Tag') -> None:
        """Replace this tag with another tag with error handling."""
        if self.parent:
            try:
                index = self.parent.contents.index(self)
                self.parent.contents[index] = new_tag
                new_tag.parent = self.parent
            except ValueError:
                pass

    def wrap(self, wrapper_tag: 'Tag') -> 'Tag':
        """Wrap this tag in another tag."""
        if self.parent:
            idx = self.parent.contents.index(self)
            self.parent.contents[idx] = wrapper_tag
            wrapper_tag.parent = self.parent
        else:
            wrapper_tag.parent = None
        wrapper_tag.contents.append(self)
        self.parent = wrapper_tag
        return wrapper_tag

    def unwrap(self) -> None:
        """Remove this tag but keep its contents in the parent."""
        if self.parent:
            idx = self.parent.contents.index(self)
            for child in reversed(self.contents):
                child.parent = self.parent
                self.parent.contents.insert(idx, child)
            self.parent.contents.remove(self)
            self.parent = None
            self.contents = []

    def insert_before(self, new_element: 'Tag') -> None:
        """Insert a tag or string immediately before this tag."""
        if self.parent:
            idx = self.parent.contents.index(self)
            new_element.parent = self.parent
            self.parent.contents.insert(idx, new_element)

    def insert_after(self, new_element: 'Tag') -> None:
        """Insert a tag or string immediately after this tag."""
        if self.parent:
            idx = self.parent.contents.index(self)
            new_element.parent = self.parent
            self.parent.contents.insert(idx + 1, new_element)

    @property
    def descendants(self):
        """Yield all descendants in document order."""
        for child in self.contents:
            yield child
            if isinstance(child, Tag):
                yield from child.descendants

    @property
    def parents(self):
        """Yield all parents up the tree."""
        current = self.parent
        while current:
            yield current
            current = current.parent

    @property
    def next_element(self):
        """Return the next element in document order."""
        if self.contents:
            return self.contents[0]
        current = self
        while current.parent:
            idx = current.parent.contents.index(current)
            if idx + 1 < len(current.parent.contents):
                return current.parent.contents[idx + 1]
            current = current.parent
        return None

    @property
    def previous_element(self):
        """Return the previous element in document order."""
        if not self.parent:
            return None
        idx = self.parent.contents.index(self)
        if idx > 0:
            prev = self.parent.contents[idx - 1]
            while isinstance(prev, Tag) and prev.contents:
                prev = prev.contents[-1]
            return prev
        return self.parent

    def decode_contents(self, eventual_encoding='utf-8') -> str:
        """
        Decode the contents of the tag to a string.

        Args:
            eventual_encoding (str, optional): Encoding to use

        Returns:
            str: Decoded contents
        """
        return ''.join(str(content) for content in self.contents)

    def prettify(self, formatter='minimal') -> str:
        """
        Return a nicely formatted representation of the tag.

        Args:
            formatter (str, optional): Formatting style

        Returns:
            str: Prettified tag representation
        """
        def _prettify(tag, indent=0):
            result = ' ' * indent + f'<{tag.name}'
            for k, v in tag.attrs.items():
                result += f' {k}="{v}"'
            result += '>\n'

            for content in tag.contents:
                if isinstance(content, Tag):
                    result += _prettify(content, indent + 2)
                else:
                    result += ' ' * (indent + 2) + str(content) + '\n'

            result += ' ' * indent + f'</{tag.name}>\n'
            return result

        return _prettify(self)
