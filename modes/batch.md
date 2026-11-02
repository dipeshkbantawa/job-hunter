# Mode: batch (this week's best jobs, forms prefilled, you submit)

For working through several fresh jobs in one sitting. Quality still comes first: the daily limit is a ceiling, not a
target, and nothing is ever submitted for the user.

1. `.venv\Scripts\python.exe -m hunter search --days 7 --no-open`: company boards and job feeds, last 7 days only.
2. `.venv\Scripts\python.exe -m hunter list --limit 30`, then shortlist. The score only counts keywords, so read each
   job description (`hunter jd <id>`) and drop any that hit a `modes/evaluate.md` gate or need skills `cv.yaml` lacks.
   Give the user the shortlist with one line of reasoning for each and let them choose.
3. For each job the user picks, write `applications/<id>-<slug>/answers.md` as in `modes/answers.md`, and tailor a CV
   (`modes/tailor.md`) if they want one. Use `modes/evaluate.md` for any job they are unsure about.
4. Ask the user to review the answers, then run `hunter apply <id> <id> ...`. It opens each form, fills the contact
   details and answers and attaches the files. The user checks everything and clicks Submit.
5. Empty fields are saved to `questions.md`. Answer the long ones in `answers.md` (`modes/answers.md`), and the user
   presses Enter in the terminal to fill them.
