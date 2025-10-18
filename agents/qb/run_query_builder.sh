#!/bin/bash
# Run Stage 3: BigQuery SQL Generation

set -e

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Load environment variables
if [ -f "$PROJECT_ROOT/.env" ]; then
    export $(cat "$PROJECT_ROOT/.env" | grep -v '^#' | xargs)
fi

cat << 'EOF'

╔═══════════════════════════════════════════════════════════════════╗
║     STAGE 3: BIGQUERY SQL GENERATION                             ║
╚═══════════════════════════════════════════════════════════════════╝

This generates validated BigQuery SQL from your cohort definition.

Input: projects/run/complete_cohort_output.json
Output: projects/qb/generated_cohort_query.sql

EOF

# Check if input exists
if [ ! -f "$PROJECT_ROOT/projects/run/complete_cohort_output.json" ]; then
    echo "❌ Error: No cohort definition found."
    echo ""
    echo "💡 Run Stage 1 + Stage 2 first:"
    echo "   cd $PROJECT_ROOT/projects/run"
    echo "   ./run_integrated.sh"
    exit 1
fi

echo "✅ Input file found"
echo ""

# Run the Python script
cd "$PROJECT_ROOT"
uv run python projects/qb/create_bigquery_sql.py

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ DONE!"
echo ""
echo "📂 Files created:"
echo "   • projects/qb/generated_cohort_query.sql"
echo "   • projects/qb/sql_generation_result.json"
echo ""
echo "💡 Next steps:"
echo "   1. Review the SQL"
echo "   2. Run it in BigQuery console"
echo "   3. Export results for analysis"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
