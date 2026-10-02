# Renders `gh issue view --json number,title,body,comments` as a ticket for the agents' prompts.
# Comments come only from the repo's owners, members and collaborators, such as a triage brief,
# because anyone can comment on a public repo.
"## Ticket #\(.number): \(.title)\n\n\(.body)\n",
(.comments
  | map(select(.authorAssociation | IN("OWNER", "MEMBER", "COLLABORATOR")))
  | select(length > 0)
  | "### Comments from maintainers\n", (.[] | "@\(.author.login) wrote:\n\n\(.body)\n"))
