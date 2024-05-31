"""Gets and parses votecount."""

import logging

from dataclasses import dataclass, field
from typing import Any, Final, Self

import httpx

logger = logging.getLogger(__name__)

NO_VOTE: Final[str] = "NO_VOTE"


@dataclass(slots=True)
class Voter:
    """Voter object"""

    name: str
    vote: str
    post: int | None
    topic_of_post: int | None

    def __post_init__(self):
        self.name = self.name.strip()
        self.vote = self.vote.strip()

    @staticmethod
    def normalize_name(
        name: str,
        alive: list[str],
        unique_voter_substring_match: bool,
        min_voter_substring_length: int,
    ) -> str | None:
        """Normalizes a name given a player list"""
        if name in alive:
            return name

        candidates: list[str] = []
        for living in alive:
            if name.lower() == living.lower():
                return living

            if (
                len(name) >= min_voter_substring_length
                and name.lower() in living.lower()
            ):
                candidates.append(living)

        if len(candidates) >= 1:
            if unique_voter_substring_match and len(candidates) > 1:
                return None
            return candidates[0]

        return None

    @classmethod
    def normalize_vote(
        cls,
        vote: str,
        alive: list[str],
        keep_unknown_votes: bool,
        unique_voter_substring_match: bool,
        min_voter_substring_length: int,
    ) -> str:
        """Normalizes a vote."""
        if vote == NO_VOTE:
            return vote

        n_vote: str | None = cls.normalize_name(
            vote, alive, unique_voter_substring_match, min_voter_substring_length
        )
        if n_vote is None:
            if keep_unknown_votes:
                return vote
            return NO_VOTE

        return n_vote

    @classmethod
    def from_json(
        cls,
        data: Any,
        alive: list[str],
        topic: int | None,
        keep_unknown_votes: bool,
        unique_voter_substring_match: bool,
        min_voter_substring_length: int,
    ) -> Self | None:
        """Returns instance from JSON data"""

        name: str
        vote: str
        post: int | None
        n_name: str | None
        match data:
            case {"voter": str(name_), "votes": list(votes), "post": int(post_)}:
                name = name_
                vote = votes[0]
                post = post_
            case {"voter": str(name_), "votes": list(votes)}:
                name = name_
                vote = votes[0]
                post = None
            case _:
                return None

        n_name = cls.normalize_name(
            name, alive, unique_voter_substring_match, min_voter_substring_length
        )
        if n_name is None:
            logger.warning("Skipping %s: Name could not be normalized.", name)
            return None
        return cls(
            name=name,
            vote=cls.normalize_vote(
                vote,
                alive,
                keep_unknown_votes,
                unique_voter_substring_match,
                min_voter_substring_length,
            ),
            post=post,
            topic_of_post=topic if post is not None else None,
        )

    def name_as_link(self, url: str, topic: int, bold: bool) -> str:
        """Formats self as a link if post is not None"""
        if self.post is None:
            return self.name

        topic_: int
        if self.topic_of_post is None:
            topic_ = topic
            logger.warning(
                "Voter %s had a post set, but not topic. This is weird.", self.name
            )
        else:
            topic_ = self.topic_of_post

        link: str = f"[{self.name}]({url}/t/{topic_}/{self.post})"
        if bold:
            return f"**{link}**"

        return link


@dataclass(slots=True)
class Votecount:
    """Votecount"""

    all_voters: dict[str, Voter] = field(default_factory=dict)
    voted: dict[str, list[Voter]] = field(default_factory=dict)
    not_voting: list[Voter] = field(default_factory=list)
    unknown: list[Voter] = field(default_factory=list)


@dataclass(slots=True)
class VotecountClient:
    """Fetches and parse votecounts."""

    url: str
    topic: int
    keep_unknown_votes: bool
    unique_voter_substring_match: bool
    min_voter_substring_length: int
    last_vc: Votecount | None = None

    def get_data_from_post(self, post: int) -> Any:
        """Gets votecount data from post number."""

        response: httpx.Response = httpx.get(
            f"{self.url}/votecount/{self.topic}/{post}.json",
            follow_redirects=True,
        )
        return response.raise_for_status().json()

    def _process_data(self, data: Any) -> list[Voter] | None:
        """Parse raw JSON data and return dict"""
        voters: list[Voter] = []
        match data:
            case {"votecount": list(votecount), "alive": list(alive)}:
                for v in votecount:
                    voter: Voter | None = Voter.from_json(
                        v,
                        alive,
                        self.topic,
                        self.keep_unknown_votes,
                        self.unique_voter_substring_match,
                        self.min_voter_substring_length,
                    )
                    if voter is not None:
                        voters.append(voter)
            case _:
                logger.error(
                    "Votecounter data from plugin could not be parsed: %s", data
                )
                return None

        return voters

    def new_vc_from_post(self, post: int) -> Votecount | None:
        """Generates new votecount from post number."""

        try:
            data = self.get_data_from_post(post)
        except httpx.RequestError as e:
            logger.exception("Encountered an HTTP request error", exc_info=e)
            return None

        voters: list[Voter] | None = self._process_data(data)
        if voters is None:
            return None

        vc: Votecount = Votecount()
        vc.all_voters = {v.name: v for v in voters}

        for voter in voters:
            # Re-use post from last VC if the target is same and post is missing
            if (
                self.last_vc is not None
                and voter.post is None
                and voter.name in self.last_vc.all_voters
                and voter.vote == self.last_vc.all_voters[voter.name].vote
                and self.last_vc.all_voters[voter.name].post is not None
            ):
                voter.post = self.last_vc.all_voters[voter.name].post
                voter.topic_of_post = self.last_vc.all_voters[voter.name].topic_of_post

            if voter.vote == NO_VOTE:
                vc.not_voting.append(voter)
                continue

            if voter.vote not in vc.all_voters:
                vc.unknown.append(voter)
                continue

            if voter.vote not in vc.voted:
                vc.voted[voter.vote] = []

            vc.voted[voter.vote].append(voter)

        self.last_vc = vc
        return vc
