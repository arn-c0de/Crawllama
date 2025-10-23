"""Phone Number Intelligence Module for OSINT.

Provides:
- Phone number validation
- Format normalization
- Country/region detection
- Carrier lookup (with phonenumbers library)
- Number type identification
- Format variations
"""

import re
import logging
from typing import Dict, List, Optional

logger = logging.getLogger("crawllama")

# Try to import phonenumbers library (optional)
try:
    import phonenumbers
    from phonenumbers import geocoder, carrier
    PHONENUMBERS_AVAILABLE = True
    logger.info("phonenumbers library available")
except ImportError:
    PHONENUMBERS_AVAILABLE = False
    logger.warning("phonenumbers library not installed - using basic functionality")


class PhoneIntelligence:
    """Phone number OSINT capabilities."""

    def __init__(self):
        """Initialize phone intelligence."""
        self.has_phonenumbers = PHONENUMBERS_AVAILABLE
        logger.info(f"Phone Intelligence initialized (phonenumbers: {self.has_phonenumbers})")

    def analyze_phone(self, phone: str, region: str = None) -> Dict:
        """
        Comprehensive phone number analysis.

        Args:
            phone: Phone number (any format)
            region: Country code (e.g., 'DE', 'US') for parsing

        Returns:
            Dictionary with analysis results:
            {
                'input': str,
                'valid': bool,
                'formatted': str,
                'country': str,
                'region': str,
                'carrier': str,
                'type': str,  # mobile/fixed/voip/unknown
                'variations': List[str],
                'confidence': float
            }

        Example:
            >>> intel = PhoneIntelligence()
            >>> result = intel.analyze_phone('+49 151 12345678')
            >>> result['valid']
            True
            >>> result['country']
            'Germany'
        """
        logger.info(f"Analyzing phone: {phone}")

        results = {
            'input': phone,
            'valid': False,
            'formatted': None,
            'country': None,
            'region': region,
            'carrier': None,
            'type': 'unknown',
            'variations': [],
            'confidence': 0.0
        }

        if self.has_phonenumbers:
            # Use phonenumbers library for full analysis
            results = self._analyze_with_library(phone, region)
        else:
            # Basic analysis without library
            results = self._analyze_basic(phone, region)

        # Generate variations
        results['variations'] = self.generate_variations(phone)

        # Calculate confidence
        results['confidence'] = self._calculate_confidence(results)

        logger.info(f"Phone analysis complete: {phone} (confidence: {results['confidence']:.2f})")
        return results

    def _analyze_with_library(self, phone: str, region: str = None) -> Dict:
        """
        Analyze phone number using phonenumbers library.

        Args:
            phone: Phone number
            region: Region code

        Returns:
            Analysis dict
        """
        results = {
            'input': phone,
            'valid': False,
            'formatted': None,
            'country': None,
            'region': region,
            'carrier': None,
            'type': 'unknown',
            'variations': [],
            'confidence': 0.0
        }

        try:
            # Parse number
            parsed = phonenumbers.parse(phone, region)

            # Validate
            results['valid'] = phonenumbers.is_valid_number(parsed)

            if not results['valid']:
                logger.warning(f"Invalid phone number: {phone}")
                return results

            # Format in international format
            results['formatted'] = phonenumbers.format_number(
                parsed,
                phonenumbers.PhoneNumberFormat.INTERNATIONAL
            )

            # Get country/location
            results['country'] = geocoder.description_for_number(parsed, 'en')
            if not results['country']:
                # Fallback to region code
                results['country'] = geocoder.region_code_for_number(parsed)

            # Get carrier
            results['carrier'] = carrier.name_for_number(parsed, 'en')

            # Get number type
            num_type = phonenumbers.number_type(parsed)
            results['type'] = self._type_to_string(num_type)

            logger.debug(f"Phone analysis: {results['formatted']} - {results['country']} - {results['carrier']}")

        except phonenumbers.NumberParseException as e:
            logger.error(f"Phone parse error: {e}")
        except Exception as e:
            logger.error(f"Phone analysis error: {e}")

        return results

    def _analyze_basic(self, phone: str, region: str = None) -> Dict:
        """
        Basic phone analysis without phonenumbers library.

        Args:
            phone: Phone number
            region: Region code (used for context)

        Returns:
            Basic analysis dict
        """
        results = {
            'input': phone,
            'valid': False,
            'formatted': None,
            'country': None,
            'region': region,
            'carrier': None,
            'type': 'unknown',
            'variations': [],
            'confidence': 0.0
        }

        # Normalize (remove spaces, dashes, parentheses)
        normalized = self._normalize_phone(phone)

        # Basic validation: must have 7-15 digits
        if re.match(r'^\+?\d{7,15}$', normalized):
            results['valid'] = True
            results['formatted'] = normalized

            # Try to detect country from prefix
            if normalized.startswith('+49'):
                results['country'] = 'Germany'
            elif normalized.startswith('+1'):
                results['country'] = 'USA/Canada'
            elif normalized.startswith('+44'):
                results['country'] = 'UK'
            elif normalized.startswith('+33'):
                results['country'] = 'France'
            elif region:
                results['country'] = f"Region: {region}"

            logger.info(f"Basic phone validation: {normalized}")
        else:
            logger.warning(f"Invalid phone format: {phone}")

        return results

    def _normalize_phone(self, phone: str) -> str:
        """
        Normalize phone number to digits only (keep +).

        Args:
            phone: Phone number

        Returns:
            Normalized phone number

        Example:
            >>> intel = PhoneIntelligence()
            >>> intel._normalize_phone('(030) 123-4567')
            '0301234567'
        """
        # Remove everything except digits and +
        normalized = re.sub(r'[^\d+]', '', phone)
        return normalized

    def _type_to_string(self, num_type: int) -> str:
        """
        Convert phonenumbers type enum to string.

        Args:
            num_type: phonenumbers number type enum

        Returns:
            Type string
        """
        types = {
            0: 'fixed_line',
            1: 'mobile',
            2: 'fixed_line_or_mobile',
            3: 'toll_free',
            4: 'premium_rate',
            5: 'shared_cost',
            6: 'voip',
            7: 'personal_number',
            8: 'pager',
            9: 'uan',
            10: 'voicemail',
            -1: 'unknown'
        }
        return types.get(num_type, 'unknown')

    def generate_variations(self, phone: str) -> List[str]:
        """
        Generate phone number format variations.

        Args:
            phone: Phone number

        Returns:
            List of format variations

        Example:
            >>> intel = PhoneIntelligence()
            >>> variations = intel.generate_variations('+49 151 12345678')
            >>> len(variations) > 1
            True
        """
        normalized = self._normalize_phone(phone)
        variations = [phone, normalized]

        # Remove country code variants
        if normalized.startswith('+'):
            # International format
            variations.append(normalized)
            # Without +
            variations.append(normalized[1:])

        # German-specific formats
        if normalized.startswith('+49'):
            # Replace +49 with 0
            variations.append('0' + normalized[3:])

            # With spaces (German format)
            if len(normalized) >= 12:
                # +49 151 12345678
                variations.append(f"+49 {normalized[3:6]} {normalized[6:]}")
                # 0151 12345678
                variations.append(f"0{normalized[3:6]} {normalized[6:]}")

        # USA format
        elif normalized.startswith('+1') and len(normalized) == 12:
            # (555) 123-4567
            area = normalized[2:5]
            exchange = normalized[5:8]
            number = normalized[8:]
            variations.append(f"({area}) {exchange}-{number}")
            variations.append(f"{area}-{exchange}-{number}")

        # Remove duplicates
        variations = list(set(variations))

        logger.debug(f"Generated {len(variations)} phone variations")
        return variations

    def _calculate_confidence(self, results: Dict) -> float:
        """
        Calculate confidence score for phone analysis.

        Args:
            results: Analysis results dict

        Returns:
            Confidence score (0.0 - 1.0)
        """
        score = 0.0

        # Valid number
        if results['valid']:
            score += 0.4

        # Has country info
        if results['country']:
            score += 0.2

        # Has carrier info (only with phonenumbers library)
        if results['carrier']:
            score += 0.2

        # Has type info
        if results['type'] != 'unknown':
            score += 0.2

        return min(score, 1.0)

    def search_phone_online(self, phone: str, max_results: int = 5) -> List[Dict]:
        """
        Search for phone number across online sources.

        Args:
            phone: Phone number
            max_results: Maximum results

        Returns:
            List of found mentions

        Note:
            Placeholder for future implementation
        """
        logger.info(f"Searching online for phone: {phone}")

        # Placeholder - would search:
        # - Various phone lookup services
        # - Social media (if public)
        # - Business directories
        # - Respecting rate limits and privacy laws

        logger.warning("Phone online search not yet implemented")
        return []
