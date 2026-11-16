# צרכנות נבונה

אתר סטטי בעברית שמציג את הדילים מהערוץ [צרכנות נבונה](https://t.me/buysmartorgohome). אין שרת ואין מסד נתונים: סקריפט מתוזמן קורא את התצוגה הציבורית `https://t.me/s/buysmartorgohome`, שומר תמונות ו־JSON בריפו, ו־GitHub Pages מגיש את האתר.

הכתובת: <https://shaydotve.github.io/buysmart-deals/>

הקישורים לדילים נשמרים בדיוק כפי שפורסמו בטלגרם. הסקרייפר לא פותח אותם ולא עוטף אותם.

גילוי נאות: חלק מהקישורים הם קישורי שותפים (כולל Amazon). רכישה דרכם עשויה לזכות את הערוץ בעמלה, בלי תוספת מחיר.

## מה צריך להפעיל בגיטהאב

אחרי המיזוג ל־`main` יש שתי הגדרות. בלי שתיהן האתר לא מתעדכן לבד.

1. **Pages.** Settings → Pages → Build and deployment → Source: **GitHub Actions**. לא לבחור Deploy from a branch.
2. **הרשאת כתיבה ל־Actions.** Settings → Actions → General → Workflow permissions → **Read and write permissions**. כך הסקרייפר יכול לשמור דילים ותמונות חדשים. בלי זה הריצה תיכשל ב־`git push`.

אחר כך: Actions → **Scrape channel** → Run workflow, פעם אחת, כדי לוודא שהמשיכה עובדת. הריצות הבאות כבר מתוזמנות.

אם בדיקת Telegram preview ב־PR נכשלת, הראנר של GitHub לא הצליח לקרוא את תצוגת הערוץ. זה לא קשור לקישורי השותפים — הבדיקה מבקשת רק את עמוד התצוגה.

## מילוי הארכיון עד 2020

האתר בריפו מתחיל מהדילים האחרונים. שאר ההיסטוריה, עד פוסט 1, רצה ידנית ובחלקים כי יש מאות עמודי תצוגה.

1. Actions → **Backfill archive** → Run workflow.
2. אפשר להשאיר 30 עמודים לריצה (בערך 20 פוסטים בעמוד, כשתי שניות בין בקשות).
3. כשהריצה ירוקה, לפתוח את הלוג ולחפש `backfill_done=`.
4. אם כתוב `backfill_done=false`, להריץ שוב. הסמן נשמר ב־`data/state.json` והריצה הבאה ממשיכה מהמקום שעצרה.
5. כשכתוב `backfill_done=true`, הארכיון הגיע לסוף.

Reset מתחיל מחדש מהעמוד החדש בלי למחוק דילים שכבר נשמרו. לא למחוק את `data/state.json` באמצע מילוי.

## לוח הזמנים, ומה קורה אחרי 60 יום שקטים

הסקרייפר רץ כל 15 דקות בחלון היום, ופעם בשעה בלילה. השעון של GitHub הוא UTC. החלון `04:00–21:59` UTC מכסה בערך `07:00–23:00` בישראל גם בשעון חורף (UTC+2) וגם בשעון קיץ (UTC+3), עם שוליים קצרים. בשאר השעות יש ריצה עגולה.

GitHub מכבה ריצות מתוזמנות אחרי **60 יום בלי שום קומיט** בריפו. כל דיל חדש או עריכה יוצרים קומיט ומאפסים את הספירה. אם הערוץ שקט חודשיים והריצות נפסקו: Actions → Scrape channel → Enable workflow, או קומיט כלשהו ל־`main`. ריצה ריקה לא שומרת קומיט, בכוונה.

ההנחה היא ריפו ציבורי, שבו דקות ה־Actions לא מחויבות. הריצה מושכת עמוד תצוגה אחד או שניים, לא את כל הארכיון.

פוש של `GITHUB_TOKEN` לא מפעיל workflow אחר. לכן סקרייפר שמצא שינוי גם מפרסם בעצמו ל־Pages, ולא סומך על הפוש שיפעיל את Deploy.

## איך האתר בנוי

- עברית, `lang=he` ו־`dir=rtl`, מובייל קודם. בלי סיידבר.
- פיד כרטיסים, חדש למעלה, בגלילה. סינון: הכל / Amazon / AliExpress / KSP, ו־«אחר» אם מופיעה חנות נוספת.
- חיפוש בדפדפן. קופון מוצג במלואו, לחיצה מעתיקה.
- עמוד קבוע לכל דיל (`/deal/<id>/`) עם תגי Open Graph, קישור לפוסט בטלגרם, וגלריה אם זה אלבום.
- מצב כהה לפי המערכת, וגם מתג.
- פוסט בלי תמונת מוצר, נעיצה, או הודעת שירות נשמרים בארכיון עם `is_deal=false` ולא נכנסים לפיד.
- תמונות יורדות מ־`telesco.pe` ל־WebP לפי מזהה הפוסט. הן מתעדכנות כשהפוסט נערך.
- `robots.txt` ו־`sitemap.xml` נוצרים עם שאר האתר.
- הנתיבים יחסיים, כדי שהאתר יעבוד תחת `/buysmart-deals/` בלי דומיין נפרד.

וידאו בלי תמונה כמעט לא מופיע בערוץ. פוסט כזה לא נכנס לפיד עד שיהיה לו קישור ותמונה.

## פיתוח מקומי

```bash
python3 -m pip install -r scraper/requirements.txt
python3 -m pytest
python3 -m scraper update --pages 2 --delay 2
python3 -m scraper build
cd site && python3 -m http.server 8765
```

הבדיקות משתמשות ב־HTML שנשמר מתוך התצוגה הציבורית, בלי רשת ובלי לפתוח קישורי שותפים.

---

# Wise shopping

A static Hebrew site for the public channel [צרכנות נבונה](https://t.me/buysmartorgohome). There is no server and no database. A scheduled script reads the public preview at `https://t.me/s/buysmartorgohome`, stores images and JSON in this repo, and GitHub Pages serves the site.

Address: <https://shaydotve.github.io/buysmart-deals/>

Deal links are kept exactly as they were posted. The scraper never requests them and never wraps them.

Disclosure: some links are affiliate links (including Amazon). A purchase through them may earn the channel a commission, at no extra cost.

## What to turn on in GitHub

After this lands on `main`, two settings have to be clicked or the site will not keep itself up to date.

1. **Pages.** Settings → Pages → Build and deployment → Source: **GitHub Actions**. Leave "Deploy from a branch" unselected.
2. **Actions write access.** Settings → Actions → General → Workflow permissions → **Read and write permissions**. The scraper commits new deals and images. Without write access, `git push` fails.

Then run Actions → **Scrape channel** → Run workflow once. Later runs are on the schedule.

If the Telegram preview check on the pull request fails, a GitHub-hosted runner could not read the channel preview. That check requests only the preview page, not affiliate links.

## Filling the archive back to 2020

The repo starts with the newest deals. The rest of the history, back to post 1, is a manual resumable job because the preview is hundreds of pages.

1. Actions → **Backfill archive** → Run workflow.
2. The default is 30 preview pages per run (about 20 posts per page, two seconds between requests).
3. When the run is green, open the log and find `backfill_done=`.
4. If it says `backfill_done=false`, run it again. The cursor lives in `data/state.json`, so the next run continues.
5. `backfill_done=true` means the crawl reached the end.

Reset starts again at the newest page and does not delete deals already stored. Leave `data/state.json` in place while a backfill is in progress.

## Schedule, and the 60-day quiet period

The scraper runs every 15 minutes during the day and hourly overnight. GitHub cron is UTC. `04:00–21:59` UTC covers about `07:00–23:00` Israel time in both winter (UTC+2) and summer (UTC+3), with a short shoulder. Other hours are hourly.

GitHub disables scheduled workflows after **60 days with no commit** in the repository. A new or edited deal produces a commit and resets that clock. If the channel is quiet for two months and the schedule stops: Actions → Scrape channel → Enable workflow, or any commit to `main`. A run that finds nothing does not create an empty commit.

This assumes a public repo, where Actions minutes are free. Each run reads one or two preview pages, not the whole archive.

A push made with `GITHUB_TOKEN` does not start another workflow. When the scraper finds a change, it deploys to Pages itself instead of waiting for that push to start Deploy.

## How the site is put together

- Hebrew, `lang=he` and `dir=rtl`, mobile first, no sidebar.
- Deal cards, newest first, loaded as you scroll. Filters: הכל / Amazon / AliExpress / KSP, plus אחר when another store shows up.
- Search runs in the browser. A coupon is shown in full and copies on tap.
- Each deal has a stable page (`/deal/<id>/`) with Open Graph tags, a link to the Telegram post, and a gallery for albums.
- Dark mode follows the system setting and can be toggled.
- Posts without a product photo, pins, and service messages stay in the archive with `is_deal=false` and stay out of the feed.
- Photos are downloaded from `telesco.pe` as WebP, keyed by post id, and replaced when the post is edited.
- `robots.txt` and `sitemap.xml` are generated with the site.
- Paths are relative, so the site works at `/buysmart-deals/` without a custom domain.

Video-only posts are rare on this channel. They stay out of the feed until a post has both a photo and an outbound link.

## Local development

```bash
python3 -m pip install -r scraper/requirements.txt
python3 -m pytest
python3 -m scraper update --pages 2 --delay 2
python3 -m scraper build
cd site && python3 -m http.server 8765
```

Tests use HTML saved from the public preview. They do not use the network and they do not open affiliate links.
