import math
import numpy as np
import scipy as sp
import json
import csv
import warnings
from typing import Literal
from numpy import testing
from collections import OrderedDict, defaultdict
from CVR import CVR
from NonnegMean import NonnegMean
import Utils

##########################################################################################    
class Audit:
    '''
    Holding place for various constants that specify what kind of contests are audited
    and how to audit them.
    '''
    
    class SOCIAL_CHOICE_FUNCTION:
        '''
        social choice functions
        '''
        SOCIAL_CHOICE_FUNCTIONS = (PLURALITY:= 'PLURALITY',
                                   SUPERMAJORITY:= 'SUPERMAJORITY',
                                   IRV:= 'IRV')
    
    class AUDIT_TYPE:
        '''
        types of audit
        '''
        AUDIT_TYPES = (POLLING:= 'POLLING',
                       BALLOT_COMPARISON:= 'BALLOT_COMPARISON'
                      ) 
        # TO DO: BATCH_COMPARISON, STRATIFIED, HYBRID, ...

##########################################################################################    
class Assertion:
    '''
    Objects and methods for SHANGRLA assertions about election outcomes

    An _assertion_ is a statement of the form
      "the average value of this assorter applied to the ballots is greater than 1/2"
    An _assorter_ maps votes to nonnegative numbers not exceeding some upper bound `u`
    '''
    # supported json assertion types for imported assertions
    JSON_ASSERTION_TYPES = (WINNER_ONLY:= "WINNER_ONLY", 
                            IRV_ELIMINATION:= "IRV_ELIMINATION") 
    def __init__(
                 self, contest: object=None, assorter: callable=None, 
                 margin: float=None, test: object=None, p_value: float=1, p_history: list=[], 
                 proved: bool=False, sample_size=None):
        '''
        assorter() should produce a float in [0, upper_bound]
        test is an instance of NonnegMean

        Parameters
        ----------
        contest: Contest instance
            contest to which the assorter is relevant
        assorter: callable
            the assorter for the assertion
        margin: float
            the assorter margin. Generally this will not be known when the assertion is created, but will be set
            later.
        test: instance of class NonnegMean
            the function to find the p-value of the hypothesis that the assertion is true, i.e., that the 
            assorter mean is <=1/2
        p_value: float
            the current p-value for the complementary null hypothesis that the assertion is false
        p_history: list
            the history of p-values, sample by sample. Generally, it is valid only for sequential risk-measuring
            functions.
        proved: boolean
            has the complementary null hypothesis been rejected?
        sample_size: int
            estimated total sample size to complete the audit of this assertion

        '''
        self.contest = contest
        self.assorter = assorter
        self.margin = margin
        self.test = test
        self.p_value = p_value
        self.p_history = p_history
        self.proved = proved
        self.sample_size = sample_size

    def __str__(self):
        return (f'contest_id: {self.contest.id} '
                f'risk function: {self.test} p-value: {self.p_value} '
                f'p-history length: {len(self.p_history)} proved: {self.proved} sample_size: {self.sample_size}'
                f'assorter upper bound: {self.assorter.upper_bound}'
               )

    def assort(self, cvr):
        return self.assorter.assort(cvr)

    def min_p(self):
        return min(self.p_history)

    def assorter_mean(self, cvr_list, use_style=True):
        '''
        find the mean of the assorter applied to a list of CVRs

        Parameters
        ----------
        cvr_list: list
            a list of cast-vote records
        use_style: Boolean
            does the audit use card style information? If so, apply the assorter only to CVRs
            that contain the contest in question.

        Returns
        -------
        mean: float
            the mean value of the assorter over the list of cvrs. If use_style, ignores CVRs that
            do not contain the contest.
        '''
        if use_style:
            filtr = lambda c: c.has_contest(self.contest.id)
        else:
            filtr = lambda c: True
        return np.mean([self.assorter.assort(c) for c in cvr_list if filtr(c)])

    def assorter_sum(self, cvr_list, use_style=True):
        '''
        find the sum of the assorter applied to a list of CVRs

        Parameters
        ----------
        cvr_list: list of CVRs
            a list of cast-vote records
        use_style: Boolean
            does the audit use card style information? If so, apply the assorter only to CVRs
            that contain the contest in question.

        Returns
        -------
        sum: float
            sum of the value of the assorter over a list of CVRs. If use_style, ignores CVRs that
            do not contain the contest.
        '''
        if use_style:
            filtr = lambda c: c.has_contest(self.contest.id)
        else:
            filtr = lambda c: True
        return np.sum([self.assorter.assort(c) for c in cvr_list if filtr(c)])

    def assorter_margin(self, cvr_list, use_style=True):
        '''
        find the margin for a list of Cvrs.
        By definition, the margin is twice the mean of the assorter, minus 1.

        Parameters
        ----------
        cvr_list: list
            a list of cast-vote records

        Returns
        ----------
        margin: float
        '''
        return 2*self.assorter_mean(cvr_list, use_style=use_style)-1
    
    def overstatement_assorter_margin(
                                      self, assorter_margin: float=None, one_vote_overstatement_rate: float=0,
                                      cvr_list: list=None) -> float:
        '''
        find the overstatement assorter margin corresponding to an assumed rate of 1-vote overstatements
        
        Parameters
        ----------        
        assorter_margin: float
            the margin for the underlying "raw" assorter. If this is not provided, calculates it from the CVR list
        one_vote_overstatement_rate: float
            the assumed rate of one-vote overstatement errors in the CVRs
        cvr_list: list
            CVRs to calculate the assorter margin. Only used if assorter_margin is None
    
        Returns
        -------
        the overstatement assorter margin implied by the reported margin and the assumed rate of one-vote overstatements
        '''
        if assorter_margin is None:
            if cvr_list:
                assorter_margin = self.assorter_margin(cvr_list)
            else:
                raise ValueError("must provide either assorter_margin or cvr_list")
        u = self.assorter.upper_bound
        return (1-r*u/assorter_margin)/(2*u/assorter_margin-1)
    
    def overstatement_assorter_mean(
                                    self, assorter_margin: float=None, one_vote_overstatement_rate: float=0,
                                    cvr_list: list=None) -> float:
        '''
        find the overstatement assorter mean corresponding to an assumed rate of 1-vote overstatements
        
        Parameters
        ----------
        
        assorter_margin: float
            the margin for the underlying "raw" assorter. If not provided, calculated from the CVR list
        one_vote_overstatement_rate: float
            the assumed rate of one-vote overstatement errors in the CVRs
        cvr_list: list
            CVRs to calculate the assorter margin. Only used if assorter_margin is None
            
        Parameters
        ----------
        assorter_margin: float
            the margin of the raw assorter
        one_vote_overstatement_rate: float
            assumed rate of one-vote overstatements
        cvr_list: list
            list of CVR objects to calculate the assorter margin, if the assorter margin was not provided
        
        Returns
        -------
        overstatement assorter mean implied by the assorter mean and the assumed rate of 1-vote overstatements
        
        '''
        if assorter_margin is None:
            if cvr_list:
                assorter_margin = self.assorter_margin(cvr_list)
            else:
                raise ValueError("must provide either assorter_margin or cvr_list")
        return (1-r/2)/(2-assorter_margin/self.assorter.upper_bound)
    

    def overstatement(self, mvr, cvr, use_style=True):
        '''
        overstatement error for a CVR compared to the human reading of the ballot

        If use_style, then if the CVR contains the contest but the MVR does
        not, treat the MVR as having a vote for the loser (assort()=0)

        If not use_style, then if the CVR contains the contest but the MVR does not,
        the MVR is considered to be a non-vote in the contest (assort()=1/2).

        Phantom CVRs and MVRs are treated specially:
            A phantom CVR is considered a non-vote in every contest (assort()=1/2).
            A phantom MVR is considered a vote for the loser (i.e., assort()=0) in every
            contest.

        Parameters
        ----------
        mvr: Cvr
            the manual interpretation of voter intent
        cvr: Cvr
            the machine-reported cast vote record

        Returns
        -------
        overstatement: float
            the overstatement error
        '''
        if not use_style:
            overstatement = self.assorter.assort(cvr)\
                            - (self.assorter.assort(mvr) if not mvr.phantom else 0)
        elif use_style:
            if cvr.has_contest(self.contest.id):    # make_phantoms() assigns contests but not votes to phantom CVRs
                if cvr.phantom:
                    cvr_assort = 1/2
                else:
                    cvr_assort = self.assorter.assort(cvr)
                if mvr.phantom or not mvr.has_contest(self.contest.id):
                    mvr_assort = 0
                else:
                    mvr_assort = self.assorter.assort(mvr)
                overstatement = cvr_assort - mvr_assort
            else:
                raise ValueError("Assertion.overstatement: use_style==True but CVR does not contain the contest")
        return overstatement

    def overstatement_assorter(self, mvr: list=None, cvr: list=None, use_style=True) -> float:
        '''
        assorter that corresponds to normalized overstatement error for an assertion

        If `use_style = True`, then if the CVR contains the contest but the MVR does not,
        that is considered to be an overstatement, because the ballot is presumed to contain
        the contest.

        If `use_style == False`, then if the CVR contains the contest but the MVR does not,
        the MVR is considered to be a non-vote in the contest.

        Parameters
        -----------
        mvr: Cvr
            the manual interpretation of voter intent
        cvr: Cvr
            the machine-reported cast vote record. 

        Returns
        --------
        over: float
            (1-o/u)/(2-v/u), where
                o is the overstatement
                u is the upper bound on the value the assorter assigns to any ballot
                v is the assorter margin
        '''
        return (1-self.overstatement(mvr, cvr, use_style)/self.assorter.upper_bound)/(2-self.margin/self.assorter.upper_bound)
    
    def find_margin(self, cvr_list: list=None, use_style=False):
        '''
        find and set the assorter margin
        
        Parameters
        ----------
        cvr_list: list
            cvrs from which the sample will be drawn
        use_style: bool
            is the sample drawn only from ballots that should contain the contest?
            
        Returns
        -------
        nothing
        
        Side effects
        ------------
        sets assorter.margin
        
        '''
        amean =self.assorter_mean(cvr_list, use_style=use_style)
        if amean < 1/2:
            warnings.warn(f"assertion {a} not satisfied by CVRs: mean value is {amean}")
        self.margin = 2*amean-1
                
                
    def make_overstatement(self, overs: float, cvr_list: list=None, use_style: bool=False) -> float:
        '''
        return the numerical value corresponding to an overstatement of `overs` times the assorter upper bound `u`
        
        Parameters
        ----------
        overs: float
            the multiple of `u`
        cvr_list: list of CVR objects
            the cvrs. Only used if the assorter margin has not been set
        use_style: bool
            flag to use style information. Only used if the assorter margin has not been set
        
        Returns
        -------
        the numerical value corresponding to an overstatement of that multiple
        
        Side effects
        ------------
        sets the assorter's margin if it had not been set
        '''
        if not self.margin:
            self.find_margin(cvrs, use_style=use_style)
        return (1-overs/self.assorter.upper_bound)/(2-self.margin/self.assorter.upper_bound)
                

    def sample_size(
                    self, data: np.array=None, prefix: bool=True, rate: float=None, 
                    reps: int=None, quantile: float=0.5, seed: int=1234567890) -> int:
        '''
        Estimate sample size needed to reject the null hypothesis that the assorter mean is <=1/2,
        for the specified risk function, given the margin and--for comparison audits--assumptions 
        about the rate of overstatement errors.
        
        If `data is not None`, uses data to make the estimate. There are three strategies:
            1. if `reps is None`, tile the data to make a list of length N
            2. if `reps is not None and not prefix`, sample from the data with replacement to make `reps` lists of 
               length N
            3. if `reps is not None and prefix`, start with `data`, then draw N-len(data) times from data with 
               replacement to make `reps` lists of length N
        
        If `data is None`, constructs values from scratch. There are two strategies:
            1. Systematically interleave small and large values, starting with a small value (`reps is None`)
            2. Sample randomly from a set of such values
        The rate of small values is `rate` if `rate is not None`. If `rate is None`, for POLLING audits, gets
        the rate of small values from the margin. 
        For POLLING audits, the small values are 0 and the large values are `u`.
        For BALLOT_COMPARISON audits, the small values are the overstatement assorter for an overstatement
        of `u` and the large values are the overstatement assorter for an overstatement of 0.

        This function is for a single assorter.

        Parameters
        ----------
        data: np.array
            observations on which to base the calculation. If `data is not None`, uses them in a bootstrap
            approach, rather than simulating errors
        prefix: bool
            prefix the data, then sample or tile to produce the remaining values
        rate: float
            assumed rate of "small" values for simulations. Ignored if `data is not None`
            if `rate is None and self.contest.audit_type==POLLING` the rate of small values is inferred from the margin 
        reps: int
            if `reps is None`, builds the data systematically
            if `reps is not None`, performs `reps` simulations to estimate the `quantile` quantile of sample size.
        quantile: float
            if `reps is not None`, quantile of the distribution of sample sizes to return 
            if `reps is None`, ignored
        seed: int
            if `reps is not None`, use `seed` as the seed in numpy.random to estimate the quantile

        Returns
        -------
        sample_size: int
            sample size estimated to be sufficient to confirm the outcome if data are generated according to
            the assumptions
        
        Side effects
        ------------
        sets the sample_size attribute of the assertion
        
        '''
        assert self.margin > 0, f'Margin {self.margin} is nonpositive'        
        if data:  # use the data provided
            sample_size = self.test.sample_size(data, alpha=self.contest.risk_limit, reps=reps, 
                                                prefix=prefix, quantile=quantile, seed=seed)
        else:     # construct data. 
                  # For POLLING, values are 0 and u. 
                  # For BALLOT_COMPARISON, values are overstatement assorter values corresponding to overstatements of u or 0
            big = self.u if self.contest.audit_type == Audit.AUDIT_TYPE.POLLING else self.make_overstatement(overs=0)
            small = 0 if self.contest.audit_type == Audit.AUDIT_TYPE.POLLING else self.make_overstatement(overs=1) 
            small_rate = (rate if self.contest.audit_type == Audit.AUDIT_TYPE.BALLOT_COMPARISON 
                          else (rate if rate is not None else (1-self.margin)/2))   # rate of small values
            x = big*np.ones(self.N)
            for k in range(self.N):
                x[k] = (small if (small_rate > 0 and k % int(1/small_rate) == 0) else x[k])
            sample_size = self.test.sample_size(x, alpha=self.contest.risk_limit, reps=reps, 
                                                prefix=prefix, quantile=quantile, seed=seed)            
        self.sample_size = sam_size
        return sam_size

    @classmethod
    def make_plurality_assertions(
                                  cls, contest: object=None, winners: list=None, losers: list=None):
        '''
        Construct assertions that imply the winner(s) got more votes than the loser(s).
        
        The assertions are that every winner beat every loser: there are
        len(winners)*len(losers) pairwise assertions in all.

        Parameters
        -----------
        contest: instance of Contest
            contest to which the assertions are relevant
        winners: list
            list of identifiers of winning candidate(s)
        losers: list
            list of identifiers of losing candidate(s)

        Returns
        --------
        a dict of Assertions

        '''
        assertions = {}
        for winr in winners:
            for losr in losers:
                wl_pair = winr + ' v ' + losr
                _test = NonnegMean(test=contest.test, estim=contest.estim, g=contest.g, u=1, N=contest.cards,
                                       t=1/2, random_order=True)
                assertions[wl_pair] = Assertion(contest.id, Assorter(contest=contest, 
                                      assort = lambda c, contest_id=contest.id, winr=winr, losr=losr:
                                      (CVR.as_vote(c.get_vote_for(contest.id, winr))
                                      - CVR.as_vote(c.get_vote_for(contest.id, losr))
                                      + 1)/2, upper_bound=1), test=_test)
        return assertions

    @classmethod
    def make_supermajority_assertion(
                                     cls, contest, winner, losers, test: callable=None, estim: callable=None):
        '''
        Construct assertion that winner got >= share_to_win \in (0,1) of the valid votes

        **TO DO: This method assumes there was a winner. To audit that there was no winner requires
        flipping things.**

        An equivalent condition is:

        (votes for winner)/(2*share_to_win) + (invalid votes)/2 > 1/2.

        Thus the correctness of a super-majority outcome--where share_to_win >= 1/2--can
        be checked with a single assertion.

        share_to_win < 1/2 might be useful for some social choice functions, including
        primaries where candidates who receive less than some threshold share are
        eliminated.

        A CVR with a mark for more than one candidate in the contest is considered an
        invalid vote.

        Parameters
        -----------
        contest: 
            contest object instance to which the assertion applies
        winner:
            identifier of winning candidate
        losers: list
            list of identifiers of losing candidate(s)
        share_to_win: float
            fraction of the valid votes the winner must get to win
        test: instance of NonnegMean
            risk function for the contest
        estim: an estimation method of NonnegMean
            estimator the test uses for the alternative

        Returns
        --------
        a dict containing one Assertion

        '''
        assertions = {}
        wl_pair = winner + ' v all'
        cands = losers.copy()
        cands.append(winner)
        _test = NonnegMean(test=test, estim=estim, u=1/(2*contest.share_to_win), N=contest.cards, t=1/2, random_order=True)
        assertions[wl_pair] = Assertion(contest.id, \
                                 Assorter(contest=contest, 
                                          assort = lambda c, contest_id=contest.id: 
                                                CVR.as_vote(c.get_vote_for(contest.id, winner))/(2*contest.share_to_win) 
                                                if c.has_one_vote(contest.id, cands) else 1/2,
                                          upper_bound = 1/(2*contest.share_to_win)), test=_test)
        return assertions

    @classmethod
    def make_assertions_from_json(
                                  cls, contest: object=None, candidates: list=None, 
                                  json_assertions: dict=None, test: callable=None, 
                                  estim: callable=None):
        '''
        dict of Assertion objects from a RAIRE-style json representations of assertions.

        The assertion_type for each assertion must be one of the JSON_ASSERTION_TYPES
        (class constants).

        Parameters
        ----------
        contest: Contest instance
            contest to which the assorter applies
        candidates:
            list of identifiers for all candidates in relevant contest.
        json_assertions:
            Assertions to be tested for the relevant contest.
        test: instance of NonnegMean
            risk function for the contest
        estim: an estimation method of NonnegMean
            estimator the test uses for the alternative

        Returns
        -------
        dict of assertions for each assertion specified in 'json_assertions'.
        '''
        assertions = {}
        for assrtn in json_assertions:
            winr = assrtn['winner']
            losr = assrtn['loser']
            if assrtn['assertion_type'] == cls.WINNER_ONLY:
                # CVR is a vote for the winner only if it has the
                # winner as its first preference
                winner_func = lambda v, contest_id=contest.id, winr=winr: 1 \
                              if v.get_vote_for(contest_id, winr) == 1 else 0

                # CVR is a vote for the loser if they appear and the
                # winner does not, or they appear before the winner
                loser_func = lambda v, contest_id=contest.id, winr=winr, losr=losr: \
                             v.rcv_lfunc_wo(contest_id, winr, losr)

                wl_pair = winr + ' v ' + losr
                _test = NonnegMean(test=test, estim=estim, u=1, N=contest.cards, t=1/2, random_order=True)               
                assertions[wl_pair] = Assertion(contest, 
                                                Assorter(contest_id=contest.id, winner=winner_func, 
                                                   loser=loser_func, upper_bound=1), test=_test)

            elif assrtn['assertion_type'] == cls.IRV_ELIMINATION:
                # Context is that all candidates in 'eliminated' have been
                # eliminated and their votes distributed to later preferences
                elim = [e for e in assrtn['already_eliminated']]
                remn = [c for c in candidates if c not in elim]
                # Identifier for tracking which assertions have been proved
                wl_given = winr + ' v ' + losr + ' elim ' + ' '.join(elim)
                _test = NonnegMean(test=test, estim=estim, u=1, N=contest.cards, t=1/2, random_order=True)               
                assertions[wl_given] = Assertion(contest, Assorter(contest_id=contest.id, 
                                       assort = lambda v, contest_id=contest.id, winr=winr, losr=losr, remn=remn:
                                       ( v.rcv_votefor_cand(contest, winr, remn)
                                       - v.rcv_votefor_cand(contest, losr, remn) +1)/2,
                                       upper_bound=1), test=_test)
            else:
                raise NotImplemented(f'JSON assertion type {assertn["assertion_type"]} not implemented.')
        return assertions

    @classmethod
    def make_all_assertions(cls, contests: dict):
        '''
        Construct all the assertions to audit the contests and add the assertions to the contest dict

        Parameters
        ----------
        contests: dict
            dict of Contest objects

        Returns
        -------
        True

        Side Effects
        ------------
        creates assertions and adds the dict of assertions relevant to each contest to the contest 
        object's `assertions` attribute

        '''
        for c in contests:
            scf = contests[c].choice_function
            winrs = contests[c].reported_winners
            losrs = [cand for cand in contests[c].candidates if cand not in winrs]
            test = contests[c].test  
            estim = contests[c].estim
            if scf == Audit.SOCIAL_CHOICE_FUNCTION.PLURALITY:
                contests[c].assertions = Assertion.make_plurality_assertions(contest=c, winners=winrs, losers=losrs, 
                                                                                test=test, estim=estim)
            elif scf == Audit.SOCIAL_CHOICE_FUNCTION.SUPERMAJORITY:
                contests[c].assertions = Assertion.make_supermajority_assertion(contest=c, winners=winrs[0], 
                                                    losers=losrs, share_to_win=contests[c].share_to_win, 
                                                    test=test, estim=estim)
            elif scf == Audit.SOCIAL_CHOICE_FUNCTION.IRV:
                # Assumption: contests[c].assertion_json yields list assertions in JSON format.
                contests[c].assertions = Assertion.make_assertions_from_json(contest=c, 
                                                    candidates=contests[c].candidates,
                                                    json_assertions=contests[c].assertion_json, 
                                                    test=test, estim=estim)
            else:
                raise NotImplementedError(f'Social choice function {scf} is not implemented.')
        return True

    @classmethod
    def set_all_margins(cls, contests: dict, cvr_list: list, use_style: bool):
        '''
        Find all the assorter margins in a set of Assertions. Updates the dict of dicts of assertions
        and the contest dict.

        Appropriate only if cvrs are available. Otherwise, base margins on the reported results.

        This function is primarily about side-effects on the assertions in the contest dict.

        Parameters
        ----------
        contests: dict of contest data, including assertions
        cvr_list: list
            list of cvr objects
        use_style: bool
            flag indicating the sample will use style information to target the contest

        Returns
        -------
        min_margin: float
            smallest margin in the audit
        '''
        min_margin = np.infty
        for c in contests:
            contests[c].margins = {}
            for a in contests[c].assertions:
                contests[c].assertions[a].margin = (margin:= contests[c].assertions[a].find_margin(use_style=use_style))
                contests[c].margins.update({a: margin})
                min_margin = min(min_margin, margin)
        return min_margin

    @classmethod
    def set_all_p_values(cls, contests: dict, mvr_sample: list, cvr_sample: list=None) -> float :
        '''
        Find the p-value for every assertion and update assertions & contests accordingly

        update p_value, p_history, proved flag, the maximum p-value for each contest.

        Primarily about side-effects.

        Parameters
        ----------
        contests: dict of dicts
            the contest data structure. outer keys are contest identifiers; inner keys are assertions

        mvr_sample: list of CVR objects
            the manually ascertained voter intent from sheets, including entries for phantoms

        cvr_sample: list of CVR objects
            the cvrs for the same sheets, for ballot-level comparison audits
            not needed for polling audits

        Returns
        -------
        p_max: float
            largest p-value for any assertion in any contest

        Side-effects
        ------------
        Sets contest max_p to be the largest P-value of any assertion for that contest
        Updates p_value, p_history, and proved for every assertion

        '''
        if cvr_sample is not None:
            assert len(mvr_sample) == len(cvr_sample), "unequal numbers of cvrs and mvrs"
        p_max = 0
        for c in contests.keys():
            contests[c].p_values = {}
            contests[c].proved = {}
            contest_max_p = 0
            use_style = contests[c].use_style
            for a in contests[c].assertions:
                asrt = contests[c].assertions[a]
                margin = asrt.margin
                upper_bound = asrt.assorter.upper_bound
                if contests[c].audit_type == Audit.AUDIT_TYPE.BALLOT_COMPARISON:
                    d = [asrt.overstatement_assorter(mvr_sample[i], cvr_sample[i],
                                margin, use_style=use_style) for i in range(len(mvr_sample)) 
                                if ((not use_style) or cvr_sample[i].has_contest(c))]
                    u = 2/(2-margin/upper_bound)
                elif contests[c].audit_type == Audit.AUDIT_TYPE.POLLING:  # polling audit. Assume style information is irrelevant
                    d = [asrt.assort(mvr_sample[i]) for i in range(len(mvr_sample))]
                    u = upper_bound
                else:
                    raise NotImplementedError(f'audit type {contests[c].audit_type} not implemented')
                contests[c].assertions[a].p_value, contests[c].assertions[a].p_history = \
                                                asrt.test.test(d)
                contests[c].assertions[a].proved = ((
                                                contests[c].assertions[a].p_value <= contests[c].risk_limit) 
                                                or contests[c].assertions[a].proved)
                contests[c].p_values.update({a: contests[c].assertions[a].p_value})
                contests[c].proved.update({a: int(contests[c].assertions[a].proved)})
                contest_max_p = np.max([contest_max_p, contests[c].assertions[a].p_value])
            contests[c].max_p = contest_max_p
            p_max = np.max([p_max, contests[c].max_p])
        return p_max


##########################################################################################    
class Assorter:
    '''
    Class for generic Assorter.

    An assorter must either have an `assort` method or both `winner` and `loser` must be defined
    (in which case assort(c) = (winner(c) - loser(c) + 1)/2. )

    Class parameters:
    -----------------
    contest: string
        identifier of the contest to which this Assorter applies

    winner: callable
        maps a dict of selections into the value 1 if the dict represents a vote for the winner

    loser : callable
        maps a dict of selections into the value 1 if the dict represents a vote for the winner

    assort: callable
        maps dict of selections into float

    upper_bound: float
        a priori upper bound on the value the assorter assigns to any dict of selections

    The basic method is assort, but the constructor can be called with (winner, loser)
    instead. In that case,

        assort = (winner - loser + 1)/2

    '''

    def __init__(
                 self, contest_id: object=None, assort: callable=None, winner: str=None, 
                 loser: str=None, upper_bound: float=1):
        '''
        Constructs an Assorter.

        If assort is defined and callable, it becomes the class instance of assort

        If assort is None but both winner and loser are defined and callable,
           assort is defined to be 1/2 if winner=loser; winner, otherwise


        Parameters
        -----------
        assort: callable
            maps a dict of votes into [0, upper_bound]
        winner: callable
            maps a pattern into [0, 1]
        loser : callable
            maps a pattern into [0, 1]
        '''
        self.contest_id = contest_id
        self.winner = winner
        self.loser = loser
        self.upper_bound = upper_bound
        if assort is not None:
            assert callable(assort), "assort must be callable"
            self.assort = assort
        else:
            assert callable(winner), "winner must be callable if assort is None"
            assert callable(loser),  "loser must be callable if assort is None"
            self.assort = lambda cvr: (self.winner(cvr) - self.loser(cvr) + 1)/2
            
    def __str__(self):
        '''
        string representation
        '''
        return f'contest_id: {self.contest_id}\nupper bound: {self.upper_bound}, ' +\
               f'winner defined: {callable(self.winner)}, loser defined: {callable(self.loser)}, ' +\
               f'assort defined: {callable(self.assort)}'
        
        

##########################################################################################    
class Contest:
    '''
    Objects and methods for contests. 
    '''
    
    ATTRIBUTES = (
                  'id',
                  'name',
                  'risk_limit',
                  'cards',
                  'choice_function',
                  'n_winners',
                  'share_to_win',
                  'candidates',
                  'reported_winners',
                  'assertion_file',
                  'audit_type',
                  'test',
                  'g',
                  'use_style',
                  'assertions',
                  'sample_size'
                 )
    
    def __init__(
                 self, 
                 id: object=None, 
                 name: str=None, 
                 risk_limit: float=0.05, 
                 cards: int=0, 
                 choice_function: str=Audit.SOCIAL_CHOICE_FUNCTION.PLURALITY, 
                 n_winners: int=1, 
                 share_to_win: float=None, 
                 candidates: list=None, 
                 reported_winners: list=None,
                 assertion_file: str=None, 
                 audit_type: str=Audit.AUDIT_TYPE.BALLOT_COMPARISON,
                 test: callable=None, 
                 g: float=0.1
                 estim: callable=None, 
                 use_style: bool=True, 
                 assertions: dict=None,
                 sample_size: int=None):
        self.id = id
        self.name = name
        self.risk_limit = risk_limit
        self.cards = cards
        self.choice_function = choice_function
        self.n_winners = n_winners
        self.share_to_win = share_to_win
        self.candidates = candidates
        self.reported_winners = reported_winners
        self.assertion_file = assertion_file
        self.audit_type = audit_type
        self.test = test
        self.g=g
        self.estim = estim
        self.use_style = use_style
        self.assertions = assertions
        self.sample_size = sample_size

    def __str__(self): 
        return str(self.__dict__)
                          

    def sample_size(self, reps: int=None, quantile: float=0.5, seed: int=1234567890, **kwargs) -> int:
        '''
        Find the initial sample size to confirm the contest at its risk limit.
        
        Parameters
        ----------
        reps: int
            number of replications for simulations.
            if `reps is None` uses a deterministic method
        quantile: float
            quantile of sample size to report for simulations
        seed: int
            seed for Mersenne Twister PRNG for simulations
        kwargs: dict
            error_rate_1: float
                assumed rate of 1-vote overstatements, for comparison audits
            error_rate_2: float
                assumed rate of 2-vote overstatements, for comparison audits
        '''
        self.sample_size = 0
        for a in self.assertions:
            self.sample_size = max(self.sample_size, 
                                   a.sample_size(rate=rate, reps=reps, quantile=quantile, seed=seed))
        return self.sample_size                   
                            

    @classmethod
    def from_dict(cls, d: dict) -> dict:
        '''
        define a contest objects from a dict containing data for one contest
        '''
        contest = Contest()
        for att in Contest.ATTRIBUTES:
            contest.__dict__[att] = d.get(att)
        return contest
    
    @classmethod
    def from_dict_of_dicts(cls, d: dict) -> dict:
        '''
        define a dict of contest objects from a dict of dicts, each inner dict containing data for one contest
        '''
        contests = {}
        for di, v in d.items():
            contests[di] = cls.from_dict(v)
        return contests
                
    @classmethod
    def initial_sample_size(
                    cls, contests: dict, rate: float=None, reps: int=None, quantile: float=0.5, 
                    seed: int=1234567890) -> int:
        '''
        Find initial sample size: maximum across assertions for all contests.

        Parameters
        ----------
        contests: dict of dicts
            each entry is a contest; each contest contains assorters, etc.
        rate: float
            assumed rate of u-vote overstatements for Audit.AUDIT_TYPE.BALLOT_COMPARISON audits
            overrides the margin for Audit.AUDIT_TYPE.POLLING audits
        reps: int
            number of random replications to use for simulating sample sizes.
            if `reps is None`, uses a deterministic estimate
        quantile: float
            if `reps is not None`, uses replications to estimate this quantile of sample size
        seed: int
            seed for the Mersenne Twister PRNG for the random replications

        Returns
        -------
        total_sample_size: int
            sample size expected to be adequate to confirm all assertions for all contests
        
        Side effects
        ------------
        sets sample_size for every assertion and every contest
        '''
        for c in contests:
            c.sample_size = 0
            for a in contests[c].assertions:
                sam_size = a.sample_size(rate=rate, reps=reps, quantile=quantile, seed=seed)
                c.sample_size  = max(c.sample_size, sam_size)
        if use_style:
            for cvr in cvr_list:
                cvr.p = 0
                for c in contests:
                    if cvr.has_contest(c):
                        cvr.p = np.maximum(c.sample_size/c.cards, cvr.p)
            total_sample_size = np.sum(np.array([x.p for x in cvr_list]))
        else:
            total_sample_size = max(c.sample_size for c in contests)
        return total_sample_size


    @classmethod
    def new_sample_size(
                        cls, contests: dict, mvr_sample: list, cvr_sample: list=None, cvr_list: list=None, 
                        use_style: bool=True, polling: bool=False, 
                        test: object=None,
                        quantile: float=0.5, reps: int=200, seed: int=1234567890) -> tuple[int, dict]:
        '''
        Estimate sample size for each contest and overall to allow the audit to complete,
        if discrepancies continue at the rate already observed.
        
        For comparison audits only.

        Uses simulations. For speed, uses the numpy.random Mersenne Twister instead of cryptorandom.

        Parameters
        ----------
        contests: dict of dicts
            the contest data structure. outer keys are contest identifiers; inner keys are assertions

        mvr_sample: list of CVR objects
            the manually ascertained voter intent from sheets, including entries for phantoms

        cvr_sample: list of CVR objects
            the cvrs for the same sheets. For

        use_style: bool
            If True, use style information inferred from CVRs to target the sample on cards that contain
            each contest. Otherwise, sample from all cards.

        test: instance of NonnegMean
            function to calculate the p-value from overstatement_assorter values.
            Should take three arguments, the sample x, the margin m, and the number of cards N.

        quantile: float
            estimated quantile of the sample size to return

        reps: int
            number of replications to use to estimate the quantile

        seed: int
            seed for the Mersenne Twister prng

        Returns
        -------
        new_size: int
            new sample size
        sams: array of ints
            array of all sizes found in the simulation
        '''
        if use_style and cvr_list is None:
            raise ValueError("use_style==True but cvr_list was not provided.")
        if use_style:
            for cvr in cvr_list:
                if cvr.in_sample():
                    cvr.p=1
                else:
                    cvr.p=0
        prng = np.random.RandomState(seed=seed)
        sample_sizes = {c:np.zeros(reps) for c in contests.keys()}
        #set dict of old sample sizes for each contest
        old_sizes = {c:0 for c in contests.keys()}
        for c in contests:
            old_sizes[c] = np.sum(np.array([cvr.in_sample() for cvr in cvr_list if cvr.has_contest(c)]))
        for r in range(reps):
            for c in contests:
                new_size = 0
                cards = contests[c]['cards']
                #raise an error or warning if the error rate implies the reported outcome is wrong
                for a in contests[c].assertions:
                    if not contests[c].assertions[a].proved:
                        p = contests[c].assertions[a].p_value
                        margin = contests[c].assertions[a].margin
                        upper_bound = contests[c].assertions[a].assorter.upper_bound
                        u = upper_bound if polling else 2/(2-margin/upper_bound)
                        if cvr_sample:
                            d = [contests[c].assertions[a].overstatement_assorter(mvr_sample[i], cvr_sample[i],\
                                contests[c].assertions[a].margin, use_style=use_style) for i in range(len(mvr_sample))]
                        else:
                            d = [contests[c].assertions[a].assort(mvr_sample[i], use_style=use_style) \
                                 for i in range(len(mvr_sample))]
                        while p > contests[c]['risk_limit'] and new_size < cards:
                            one_more = sample_by_index(len(d), 1, prng=prng)[0]
                            d.append(d[one_more-1])
                            p = test.test(d)
                        new_size = np.max([new_size, len(d)])
                sample_sizes[c][r] = new_size
        new_sample_size_quantiles = {c:int(np.quantile(sample_sizes[c], quantile) - old_sizes[c]) for c in sample_sizes.keys()}
        if cvr_list:
            for cvr in cvr_list:
                for c in contests:
                    if cvr.has_contest(c) and not cvr.in_sample():
                        cvr.p = np.max(new_sample_size_quantiles[c] / (contests[c]['cards'] - old_sizes[c]), cvr.p)
            total_sample_size = np.round(np.sum(np.array([x.p for x in cvr_list])))
        else:
            total_sample_size = np.max(np.array(new_sample_size_quantiles.values))
        return total_sample_size, new_sample_size_quantiles
    