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
from utils.validators import sanitize_for_logging

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
        logger.info("Phone Intelligence initialized")  # lgtm[py/clear-text-logging-sensitive-data] - Details omitted

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
        # Sanitize phone number for logging (mask digits)
        logger.info(f"Analyzing phone: {sanitize_for_logging(phone, 'generic')}")

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

        logger.info(f"Phone analysis complete: {sanitize_for_logging(phone, 'generic')} (confidence: {results['confidence']:.2f})")
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
            # Auto-detect region for national format numbers
            parse_region = region
            normalized = self._normalize_phone(phone)

            if not parse_region and not normalized.startswith('+'):
                # Try to detect country from national format
                parse_region = self._detect_region(normalized)
                if parse_region:
                    logger.debug(f"Auto-detected region {parse_region} for number")

            # Parse number
            parsed = phonenumbers.parse(phone, parse_region)

            # Validate
            results['valid'] = phonenumbers.is_valid_number(parsed)

            if not results['valid']:
                logger.warning(f"Invalid phone number: {sanitize_for_logging(phone, 'generic')}")
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
            logger.warning(f"Invalid phone format: {sanitize_for_logging(phone, 'generic')}")

        return results

    def _detect_region(self, normalized: str) -> Optional[str]:
        """
        Auto-detect country region from national format number.

        Args:
            normalized: Normalized phone number

        Returns:
            Region code (e.g., 'DE', 'US', 'GB') or None

        Note:
            This tries multiple common regions and validates the number.
            Priority order: DE, GB, US, PL, FR, IT, ES, AT, CH
        """
        # Numbers starting with 0 (European national format)
        if normalized.startswith('0') and not normalized.startswith('00'):
            # Try common European regions in priority order
            regions_to_try = [
                'DE',  # Germany: 030, 040, 089, mobile 015x, 016x, 017x
                'GB',  # UK: 020 (London), 011x, mobile 07xxx
                'PL',  # Poland: 022 (Warsaw), mobile starting with 5,6,7,8
                'FR',  # France: 01-05 (landline), 06-07 (mobile)
                'IT',  # Italy: 02 (Milan), 06 (Rome), mobile 3xx
                'ES',  # Spain: 91 (Madrid), 93 (Barcelona), mobile 6x, 7x
                'AT',  # Austria: 01 (Vienna), mobile 06xx
                'CH',  # Switzerland: 0xx area codes, mobile 07x
                'NL',  # Netherlands: 020 (Amsterdam), mobile 06
                'BE',  # Belgium: 02 (Brussels), mobile 04xx
            ]

            for region in regions_to_try:
                try:
                    parsed = phonenumbers.parse(normalized, region)
                    if phonenumbers.is_valid_number(parsed):
                        logger.debug(f"Number validated for region {region}")
                        return region
                except Exception as e:
                    logger.debug(f"Failed to parse phone number for region {region}: {e}")
                    continue

        # Numbers without leading 0 (could be US/CA or other formats)
        elif normalized.isdigit() and len(normalized) == 10:
            # Likely US/Canada 10-digit format
            try:
                parsed = phonenumbers.parse(normalized, 'US')
                if phonenumbers.is_valid_number(parsed):
                    logger.debug("Number validated for region US")
                    return 'US'
            except Exception as e:
                logger.debug(f"Failed to parse 10-digit number as US format: {e}")

        logger.debug("Could not auto-detect region")
        return None

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

        # Country-specific formats (order matters: first matching country wins)
        if normalized.startswith('+49') or (normalized.startswith('0') and len(normalized) >= 10):
            variations.extend(self._german_variations(normalized))
        elif normalized.startswith('+44') or (normalized.startswith('0') and len(normalized) == 11):
            variations.extend(self._uk_variations(normalized))
        elif normalized.startswith('+48') or (normalized.startswith('0') and len(normalized) == 9):
            variations.extend(self._polish_variations(normalized))
        elif normalized.startswith('+1') or (len(normalized) == 10 and normalized[0] != '0'):
            variations.extend(self._us_variations(normalized))
        elif normalized.startswith('+33'):
            variations.extend(self._french_variations(normalized))

        # Remove duplicates and empty strings
        variations = [v for v in list(set(variations)) if v]

        logger.debug(f"Generated {len(variations)} phone variations")
        return variations

    @staticmethod
    def _german_variations(normalized: str) -> List[str]:
        """German format variations (+49 international and 0-prefixed national)."""
        if not normalized.startswith('+49'):
            # Already national format (0xxx)
            return [f"+49{normalized[1:]}"]

        # Replace +49 with 0
        variations = [f"0{normalized[3:]}"]
        # With spaces: +49 151 12345678
        if len(normalized) >= 12:
            variations.append(f"+49 {normalized[3:6]} {normalized[6:]}")
            variations.append(f"0{normalized[3:6]} {normalized[6:]}")
        return variations

    @staticmethod
    def _uk_variations(normalized: str) -> List[str]:
        """UK format variations (+44 international and 0-prefixed national)."""
        if not normalized.startswith('+44'):
            # Already national format
            return [f"+44{normalized[1:]}"]

        return [
            # Replace +44 with 0
            f"0{normalized[3:]}",
            # With spaces: +44 20 7946 0958
            f"+44 {normalized[3:5]} {normalized[5:9]} {normalized[9:]}",
        ]

    @staticmethod
    def _polish_variations(normalized: str) -> List[str]:
        """Polish format variations (+48 international and national)."""
        if not normalized.startswith('+48'):
            return [f"+48{normalized}"]

        return [
            normalized[3:],
            f"+48 {normalized[3:5]} {normalized[5:8]} {normalized[8:]}",
        ]

    @staticmethod
    def _us_variations(normalized: str) -> List[str]:
        """USA/Canada format variations (+1 international and 10-digit national)."""
        variations: List[str] = []

        if normalized.startswith('+1') and len(normalized) == 12:
            area, exchange, number = normalized[2:5], normalized[5:8], normalized[8:]
        elif len(normalized) == 10:
            area, exchange, number = normalized[0:3], normalized[3:6], normalized[6:]
            variations.append(f"+1{normalized}")
        else:
            return variations

        if area and exchange and number:
            variations.append(f"({area}) {exchange}-{number}")
            variations.append(f"{area}-{exchange}-{number}")
            variations.append(f"{area}.{exchange}.{number}")
        return variations

    @staticmethod
    def _french_variations(normalized: str) -> List[str]:
        """French format variations (+33 international and 0-prefixed national)."""
        # Replace +33 with 0
        variations = [f"0{normalized[3:]}"]
        # French format: +33 1 42 86 82 00
        if len(normalized) >= 12:
            variations.append(f"+33 {normalized[3]} {normalized[4:6]} {normalized[6:8]} {normalized[8:10]} {normalized[10:]}")
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
        logger.info(f"Searching online for phone: {sanitize_for_logging(phone, 'generic')}")

        # Placeholder - would search:
        # - Various phone lookup services
        # - Social media (if public)
        # - Business directories
        # - Respecting rate limits and privacy laws

        logger.warning("Phone online search not yet implemented")
        return []
