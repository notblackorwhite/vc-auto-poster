"""Makes new Discourse posts"""

import logging

from types import SimpleNamespace
from typing import Any, Final, Self

from pydiscourse import DiscourseClient  # type: ignore
from pydiscourse.exceptions import (  # type: ignore
    DiscourseError,
    DiscourseServerError,
    DiscourseRateLimitedError,
    DiscourseClientError,
)

from vc_autoposter.config import Config
from vc_autoposter.votecount import VotecountClient, Votecount

logger = logging.getLogger()

RETRY_ATTEMPTS: Final[int] = 3


class Poster:
    """Poster"""

    def __init__(
        self,
        url: str,
        topic: int,
        api_username: str,
        api_key: str,
        min_posts: int,
        pretty: bool,
        links: bool,
        game_name: str | None,
        suppress_tags: list[str],
        keep_unknown_votes: bool,
        unique_voter_substring_match: bool,
        min_voter_substring_length: int,
    ):
        self.url: str = url
        self.topic: int = topic
        self.api_username: str = api_username
        self.api_key: str = api_key
        self.min_posts: int = min_posts
        self.pretty: bool = pretty
        self.links: bool = links
        self.game_name: str | None = game_name
        self.suppress_tags: set[str] = set(suppress_tags)

        self.discourse_client: DiscourseClient = DiscourseClient(
            url, api_username=api_username, api_key=api_key
        )
        self.vc_client: VotecountClient = VotecountClient(
            url=url,
            topic=topic,
            keep_unknown_votes=keep_unknown_votes,
            unique_voter_substring_match=unique_voter_substring_match,
            min_voter_substring_length=min_voter_substring_length,
        )
        self.last_vc_at: int = 0

    @classmethod
    def from_config(cls, config: Config) -> Self:
        """Instantiates using a `Config`."""
        return cls(
            url=config.url,
            api_username=config.api_username,
            api_key=config.api_key,
            topic=config.topic,
            min_posts=config.min_posts,
            pretty=config.pretty,
            links=config.links,
            game_name=config.game_name,
            suppress_tags=config.suppress_tags,
            keep_unknown_votes=config.keep_unknown_votes,
            unique_voter_substring_match=config.unique_voter_substring_match,
            min_voter_substring_length=config.min_voter_substring_length,
        )

    def update_from_config(self, config: Config):
        """Updates self using a `Config`."""

        if (
            config.url != self.url
            or config.api_username != self.api_username
            or config.api_key != self.api_key
        ):
            self.discourse_client = DiscourseClient(
                config.url, api_username=config.api_username, api_key=config.api_key
            )

        if (
            config.url != self.url
            or config.topic != self.topic
            or self.vc_client.unique_voter_substring_match
            or self.vc_client.keep_unknown_votes
            != config.keep_unknown_votes
            != config.unique_voter_substring_match
            or self.vc_client.min_voter_substring_length
            != config.min_voter_substring_length
        ):
            last_vc = self.vc_client.last_vc
            self.vc_client = VotecountClient(
                url=config.url,
                topic=config.topic,
                keep_unknown_votes=config.keep_unknown_votes,
                unique_voter_substring_match=config.unique_voter_substring_match,
                min_voter_substring_length=config.min_voter_substring_length,
            )
            self.vc_client.last_vc = last_vc

        if config.topic != self.topic:
            logger.info("Topic ID changed from #%s to #%s.", self.topic, config.topic)
            self.last_vc_at = 0

        self.url = config.url
        self.topic = config.topic
        self.api_username = config.api_username
        self.api_key = config.api_key
        self.min_posts = config.min_posts
        self.pretty = config.pretty
        self.links = config.links
        self.game_name = config.game_name
        self.suppress_tags = set(config.suppress_tags)

    def get_topic_by_id(self) -> dict[str, Any]:
        """Gets topic by ID"""
        return self.discourse_client._get(f"/t/{self.topic}.json")  # type: ignore

    def vc_to_lines(self, vc: Votecount, links: bool) -> list[str]:
        """Returns self as formatted lines."""
        voted_names: dict[str, list[str]]
        not_voting_names: list[str]

        if links:
            voted_names = {
                k: [n.name_as_link(self.url, self.topic, bold=True) for n in v]
                for k, v in vc.voted.items()
            }
            for v in vc.unknown:
                if v.vote not in voted_names:
                    voted_names[v.vote] = []
                voted_names[v.vote].append(
                    v.name_as_link(self.url, self.topic, bold=True)
                )
            not_voting_names = [
                n.name_as_link(self.url, self.topic, bold=True) for n in vc.not_voting
            ]
        else:
            voted_names = {k: [n.name for n in v] for k, v in vc.voted.items()}
            for v in vc.unknown:
                if v.vote not in voted_names:
                    voted_names[v.vote] = []
                voted_names[v.vote].append(v.name)

            not_voting_names = [n.name for n in vc.not_voting]

        lines: list[str] = []
        for key in sorted(voted_names, key=lambda k: len(voted_names[k]), reverse=True):
            lines.append(
                f"**{key} ({len(voted_names[key])}):** {', '.join(voted_names[key])}"
            )

        lines.append("")
        lines.append(
            f"**Not Voting ({len(not_voting_names)}):** {', '.join(not_voting_names)}"
        )
        return lines

    def vc_to_table(self, vc: Votecount, links: bool) -> list[str]:
        """Generates a Markdown table from a Votecount"""

        header: str = "| Votes | Wagon | Voters |"
        divider: str = "|---|---|---|"
        lines: list[str] = [header, divider]

        voted_names: dict[str, list[str]]
        not_voting_names: list[str]
        unknown_names: list[str]

        if links:
            voted_names = {
                k: [n.name_as_link(self.url, self.topic, bold=True) for n in v]
                for k, v in vc.voted.items()
            }
            not_voting_names = [
                n.name_as_link(self.url, self.topic, bold=True) for n in vc.not_voting
            ]
            if self.vc_client.keep_unknown_votes:
                unknown_names = [
                    f"{n.name_as_link(self.url, self.topic, bold=True)} (for {n.vote})"
                    for n in vc.unknown
                ]
            else:
                not_voting_names += [
                    n.name_as_link(self.url, self.topic, bold=True) for n in vc.unknown
                ]
        else:
            voted_names = {k: [n.name for n in v] for k, v in vc.voted.items()}
            not_voting_names = [n.name for n in vc.not_voting]
            if self.vc_client.keep_unknown_votes:
                unknown_names = [f"{n.name} (for {n.vote})" for n in vc.not_voting]
            else:
                not_voting_names += [n.name for n in vc.unknown]

        for target in sorted(
            voted_names, key=lambda k: len(voted_names[k]), reverse=True
        ):
            lines.append(
                f"| {len(voted_names[target])} | **{target}** | {', '.join(voted_names[target])} |"
            )

        lines.append(
            f"| {len(not_voting_names)} | **Not Voting** | {', '.join(not_voting_names)}"
        )

        if len(unknown_names) > 0:
            lines.append(
                f"| {len(unknown_names)} | **Unrecognized** | {', '.join(unknown_names)}"
            )

        return lines

    def is_suppressed(self, last_post_num: int, tags: list[str], closed: bool) -> bool:
        """Checks if output should be suppressed."""
        if closed:
            logger.info("Topic is closed. Skipping.")
            return True

        if last_post_num - self.last_vc_at < self.min_posts:
            logger.info(
                (
                    "Minimum posts between VCs is %s. Posts since last (#%s) is %s. "
                    "Waiting until %s. Skipping."
                ),
                self.min_posts,
                last_post_num,
                last_post_num - self.last_vc_at,
                last_post_num + self.min_posts,
            )
            return True

        suppress_tags: set[str] = set(tags).intersection(self.suppress_tags)
        if len(suppress_tags) != 0:
            logger.info(
                "Output suppressed due to 1 or more tags (%s). Skipping.",
                ", ".join(suppress_tags),
            )
            return True

        return False

    def post_new_vc(self):
        """Posts a new VC."""
        logger.info("Attempting to post new votecount for topic ID #%s.", self.topic)

        try:
            topic: SimpleNamespace = SimpleNamespace(**self.get_topic_by_id())
        except (
            DiscourseError,
            DiscourseServerError,
            DiscourseRateLimitedError,
            DiscourseClientError,
        ) as e:
            logger.exception("Encountered a Discourse error", exc_info=e)
            return

        last_post_num: int | None = getattr(topic, "highest_post_number", None)
        if last_post_num is None:
            logger.error("Could not find latest post number.")
            return

        tags: list[str] = getattr(topic, "tags", [])

        closed: bool | None = getattr(topic, "closed", None)
        if closed is None:
            logger.warning("Couldn't get topic closed value. Assuming true.")
            closed = True

        if self.is_suppressed(last_post_num, tags, closed):
            return

        day: int | None = None

        for tag in tags:
            if tag.startswith("day-"):
                day_ = tag.split("-")[1]
                if day_.isdigit():
                    day = int(day_)
                    break

        vc: Votecount | None = self.vc_client.new_vc_from_post(last_post_num)
        if vc is None:
            logger.error(
                "Could not generate votecount using post %s in topic #%s.",
                last_post_num,
                self.topic,
            )
            return

        lines: list[str] = []

        if self.pretty:
            lines.append("[center]")
            title: str = "Votecount"
            if day is not None:
                title = f"Day {day} {title}"
            if self.game_name is not None:
                title = f"{self.game_name} {title}"
            lines.append(f"# [size=5][color=#9370db]{title}[/color][/size]")
            lines.append("[/center]")

            lines = lines + self.vc_to_table(vc, links=self.links)

            lines.append("")
            lines.append('[details="Raw VC for the plugin"]')

        lines.append("[votecount]")
        lines = lines + self.vc_to_lines(vc, links=False)
        lines.append("[/votecount]")

        if self.pretty:
            lines.append("[/details]")

        lines.append(
            (
                "\n[size=2]I'm a new bot, and I made this post. "
                "Please forgive any mistakes 😖.[/size]"
            )
        )
        lines.append("[size=2]If you're mean to me I WILL cry.[/size]")

        logger.info("Attempting to post VC to topic #%s...", self.topic)
        last_vc_at: int | None = None
        for i in range(RETRY_ATTEMPTS):
            if i != 0:
                logger.info("Retrying post...")

            try:
                response = self.discourse_client.create_post(
                    "\n".join(lines),
                    topic_id=self.topic,
                )
            except (
                DiscourseError,
                DiscourseServerError,
                DiscourseRateLimitedError,
                DiscourseClientError,
            ) as e:
                logger.exception("Encountered a Discourse error", exc_info=e)
                return
            response_ns = SimpleNamespace(**response)
            last_vc_at = getattr(response_ns, "post_number", None)
            if last_vc_at is not None:
                logger.info(
                    "VC posted successfully to topic #%s at post #%s!",
                    self.topic,
                    last_vc_at,
                )
                self.last_vc_at = last_vc_at
                return

        logger.warning(
            "VC could not be posted after %s attempts. Skipping.", RETRY_ATTEMPTS
        )
