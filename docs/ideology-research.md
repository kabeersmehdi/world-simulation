---
type: policy
title: Researching ideology, religion and doctrine
status: active
generated:
  by: human-reviewed
  at: 2026-10-18
---

# Researching ideology, religion and doctrine

Religion and doctrine shape policy in all three countries, and leaders say so themselves. This layer records **which texts and doctrines each leader, party or state invokes**, what those sources say, and how that lines up with what the actor then does.

## Method
1. **Start with the actor's own words.** A speech, a platform, a coalition agreement, a constitution, a fatwa, a ruling. That is the main source and the anchor of every record.
2. **Then the text they cite.** When a leader invokes a passage or doctrine (Torah, Talmud, Zohar and other Kabbalah, the Quran, hadith, Shia jurisprudence, the New Testament, Christian Zionist writing), record the passage, the standard readings of it, and where readings disagree.
3. **Then the behavior.** Compare the doctrine with decisions taken afterwards. Agreement strengthens the link; contradiction weakens it. Record both.
4. **Label it.** The quote is `official_position`. What the actor did is `observed_behavior`. "This doctrine drives that policy" is `evidence_backed_inference` once several cases agree, otherwise `hypothesis`, with `evidence_against` filled in.

Different believers read the same text differently, so a passage tells you what is available to a leader, and the leader's own statements tell you which reading they hold.

## Starting map
| Actor | Documented religious or doctrinal basis | Primary sources to pull |
|---|---|---|
| Iran's state | Velayat-e faqih written into the constitution (Articles 4, 5, 110); Twelver Shia jurisprudence | Constitution, the Leader's speeches and fatwas, Guardian Council rulings |
| Itamar Ben-Gvir (Otzma Yehudit) | Religious Zionism; came out of Meir Kahane's movement; positions on the Temple Mount and settlement | Party platform, ministerial statements, court rulings |
| Bezalel Smotrich (Religious Zionism) | Religious Zionist settler movement; published plans on West Bank sovereignty | His published plans, speeches, budget decisions |
| Haredi parties (Shas, United Torah Judaism) | Torah study as a religious duty; exemption of yeshiva students from military service | Coalition agreements, conscription bills, rabbinic council statements |
| Benjamin Netanyahu | Jewish; leads secular-nationalist Likud; uses biblical references in wartime speeches; depends on religious partners for a majority | Knesset and UN speeches, coalition agreements |
| Donald Trump | Christian (raised Presbyterian, now non-denominational). His religious tie to Israel runs through his evangelical and Christian Zionist base | Speeches to evangelical groups, appointments, voter surveys |

## Recording it
Each finding is an evidence record in `data/evidence/` with `topics` including `doctrine` or `religion`. Constitutional and legal doctrine also goes in `data/relationships/` with type `doctrine`.
