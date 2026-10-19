"""One advisory code review; shares the existing total budget and three-call cap."""
from review_bb3_code_with_jev import ROOT, main


if __name__ == '__main__':
    main(ROOT / 'scripts/research_bb_alternatives.py',
         ROOT / 'tests/test_bb_alternatives.py', {
             'causality': 'Signals use only information available by the signal close. A strict pivot with two right bars is only used after those bars close. Entry is the next contiguous bar open, never the pivot bar.',
             'selection': 'The visible runner evaluates exactly two predeclared alternative strategies and one original comparison, without optimizing parameters or switching to a later-year winner.',
             'separation': 'No AI response or API participates in signal generation, entry, exit, or numerical backtest calculations. This review is advisory and external to those calculations.'})
