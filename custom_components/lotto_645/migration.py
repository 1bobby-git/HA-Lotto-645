"""One-way removal of obsolete feature settings and shipped files, never user records."""
from pathlib import Path
import logging

from .methods import DEFAULT_METHOD_IDS, METHODS_BY_ID

_LOGGER = logging.getLogger(__name__)
# Exact shipped-file allowlist. No historical executor is retained for compatibility.
_REMOVED_MODULES = (
    'personal_lucky', 'portfolio', 'portfolio_runtime', 'research_runtime',
    'research_extension', 'research_formulas', 'historical_validation',
    'historical_validation_runtime', 'historical_validation_scores',
    'validation_hit_history', 'validation_lifecycle',
    'analysis', 'sampling', 'consensus', 'voting_consensus', 'saju_rules',
    'formula_settings', 'formula_cache', 'generation_runtime',
)
_REMOVED_SCRIPTS = (
    'lotto-panel-portfolio.js', 'lotto-panel-research.js',
    'lotto-panel-validation.js', 'lotto-panel-validation-details.js',
)
_REMOVED_IDS = frozenset({'personal_lucky', 'portfolio_triplet_coverage'})


def clean_options(raw: dict) -> dict:
    options = {key: value for key, value in raw.items()
               if key not in {'lucky_keyword', 'lucky_theme', 'personal_lucky', 'generation_rules', 'formula_options'}}
    for key in ('selected_methods', 'advanced_methods'):
        if isinstance(options.get(key), (list, tuple)):
            options[key] = [value for value in options[key] if value not in _REMOVED_IDS]
    if 'selected_methods' in options and not options['selected_methods'] and not options.get('advanced_methods'):
        options['selected_methods'] = list(DEFAULT_METHOD_IDS)
    return options


def cleanup_files(root: Path) -> None:
    """Clean leftovers from installers that overwrite instead of replacing folders."""
    paths = [root / (name + '.py') for name in _REMOVED_MODULES]
    paths += [root / (name + '.pyc') for name in _REMOVED_MODULES]
    paths += [root / 'www' / name for name in _REMOVED_SCRIPTS]
    paths += [root / 'www' / 'methods' / 'personal_lucky.md']
    cache = root / '__pycache__'
    for name in _REMOVED_MODULES:
        paths.extend(cache.glob(name + '.*.pyc'))
    core = root / 'lotto_core'
    core_modules = ('__init__','analysis','api','cli','consensus','const','constraints',
                    'formula_settings','methods','models','myungri','preference',
                    'saju_calendar','saju_rules','sampling','voting_consensus')
    if not core.is_symlink():
        for name in core_modules:
            paths.extend((core/(name+'.py'),core/(name+'.pyc')))
            paths.extend((core/'__pycache__').glob(name+'.*.pyc'))
    for path in paths:
        # Only unlink a shipped basename; never traverse a symlink into another folder.
        if any(parent.is_symlink() for parent in path.parents if parent == root or root in parent.parents):
            continue
        try:
            path.unlink(missing_ok=True)
        except OSError:
            _LOGGER.warning('Could not remove obsolete integration file: %s', path.name)


async def async_cleanup_removed_features(hass, entry) -> None:
    data, options = clean_options(dict(entry.data)), clean_options(dict(entry.options))
    if data != dict(entry.data) or options != dict(entry.options):
        hass.config_entries.async_update_entry(entry, data=data, options=options)
    await hass.async_add_executor_job(cleanup_files, Path(__file__).parent)
