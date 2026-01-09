# Test Data Population Script

This directory contains `populate_test_data.py`, a script to create a test user account with sample data for demonstrating HiveGuide functionality.

## What it Creates

### Test User Account
- **Email**: test@test.com
- **Password**: test123
- **Status**: Pre-approved (can login immediately)

### Hives (4 total)

Each hive has a unique story throughout the 2025 beekeeping season:

1. **Home 1** - *The Strong Producer*
   - Location: Backyard
   - Description: Original hive established in Spring 2025. Strong colony with consistent production.
   - Inspection History: 7 inspections (April - October 2025)
   - Story: Started as a package install in April, built up strong, harvested honey in August, excellent winter prep
   - Key moments: Queen marking in July, honey harvest, 50 lbs winter stores

2. **Home 2** - *The Late Bloomer*
   - Location: Backyard
   - Description: Swarm caught from Home 1 in June 2025. Growing colony with excellent temperament.
   - Inspection History: 5 inspections (June - October 2025)
   - Story: Caught as a swarm from Home 1, started later in season, racing to build up for winter
   - Key moments: Calm temperament noted, rapid growth in August, smaller stores (35 lbs) but hopeful for winter
   - Note: Starts later than other hives (caught swarm)

3. **Bee Club 1** - *The Overwintered Champion*
   - Location: Community Apiary
   - Description: Hive maintained at local bee club. Great for learning and sharing experiences.
   - Inspection History: 7 inspections (April - October 2025)
   - Story: Survived winter, prevented swarming, used for demonstrations, strong honey production
   - Key moments: Spring swarm prevention, extracted honey at club meeting, gentle temperament
   - **Latest inspection**: Alcohol wash varroa test showing 10 mites per 300 bees (3% - above threshold)

4. **Bee Club 2** - *The Problem Child*
   - Location: Community Apiary
   - Description: Second hive at bee club. Used for demonstrating inspection techniques.
   - Inspection History: 7 inspections (April - October 2025)
   - Story: Started strong but developed varroa mite issues, showing spotty brood pattern by late summer
   - Key moments: Swarm cells in June, queen marking demonstration, spotty brood pattern from mites
   - **Latest inspection**: Alcohol wash varroa test showing 13 mites per 300 bees (4% - above threshold), oxalic acid treatment applied

### Total Data
- **26 inspections** across all hives
- Casual, realistic beekeeping notes including:
  - Natural, conversational language (like voice notes)
  - Queen sightings and marking
  - Specific frame counts and observations
  - Actions taken (adding boxes, extracting honey, feeding)
  - Equipment mentions (supers, entrance reducers, feeders)
  - Seasonal progression from spring through fall
  - Problems and solutions (swarm prevention, mite issues)
  - Varroa mite testing results with treatment decisions
  - "Next steps" thinking for future inspections

## Usage

### Prerequisites
- Python 3.x installed
- Database credentials configured (DATABASE_URL environment variable or config.yaml)
- Required Python packages: sqlalchemy, passlib, pyyaml, psycopg2-binary

### Running the Script

```bash
# From the backend directory
cd backend
python3 scripts/populate_test_data.py
```

Or from the project root:

```bash
python3 backend/scripts/populate_test_data.py
```

### Expected Output

**First run:**
```
🐝 HiveGuide Test Data Population
==================================================
✅ Created test user: test@test.com
   Password: test123
✅ Created hive: Home 1 (Backyard)
   📝 Added 7 inspections
...
```

**Subsequent runs (auto-cleanup):**
```
🐝 HiveGuide Test Data Population
==================================================
🗑️  Found existing test user 'test@test.com' - cleaning up old data...
✅ Deleted old test data
✅ Created test user: test@test.com
   Password: test123
✅ Created hive: Home 1 (Backyard)
   📝 Added 7 inspections
...
```

## Behavior

- **Auto-cleanup**: If test@test.com already exists, the script automatically deletes all associated data (sessions, hives, inspections) before recreating
- **Repeatable**: You can modify the test data in the script and simply rerun it - old data is wiped out automatically
- **Database**: Connects to the PostgreSQL database specified in DATABASE_URL or config.yaml
- **Password Hashing**: Uses bcrypt to securely hash the test password
- **Safe**: Only affects the test@test.com user account - no other data is touched

## Testing the Account

After running the script, you can login to HiveGuide with:
- **Email**: test@test.com
- **Password**: test123

You should be able to:
- View all 4 hives
- See the complete inspection history for each hive
- Notice that Home 2 has fewer inspections (starts in June)
- See varroa test results in the latest Bee Club inspections (October)

## Modifying Test Data

To modify the test data:

1. Edit the `hives_data` section in `populate_test_data.py`
2. Update inspection notes, add/remove inspections, change hive details, etc.
3. Simply rerun the script - it will automatically clean up and recreate:
   ```bash
   python3 backend/scripts/populate_test_data.py
   ```

The script handles all cleanup automatically - no manual database operations needed!

## Manual Cleanup

If you prefer to manually remove test data without recreating:

```sql
-- Delete test user and all associated data (cascades to hives and inspections)
DELETE FROM users WHERE email = 'test@test.com';
```

Or use the HiveGuide admin interface to delete the user account.
