import pandas as pd
import pytest
import os
import sys

# Add execution dir to path so we can import the module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'execution')))

import process_racing_data

@pytest.fixture
def sample_csv(tmp_path):
    """Creates a sample CSV file with known data for testing."""
    data = {
        "Venue": ["Sydney", "Melbourne", "Sydney"],
        "RN": ["2", "1", "1"],
        "TN": ["5", "3", "2"],
        "Horse Name": ["Fast Horse", "Slow Horse", "Medium Horse"],
        "Today Price": ["2.50", "10.00", "5.00"],
        "Line of Betting": ["1", "5", "3"],
        "Race Group": ["G1", "Bm58", "Cl1"],
        "Race Class": ["Open", "Restricted", "Open"],
        "Today Dist": ["1200", "1400", "1000"],
        "Track Condition": ["Good", "Soft", "Heavy"],
        "No. Starters": ["10", "8", "6"],
        "Today Race PM": ["14:00", "15:00", "13:00"],
        "Comments": ["Good chance", "Can win", "Maybe"],
        "OneHundredRatings": ["95", "80", "85"],
        "Ultimrating": ["90", "70", "100"], # Highest numeric matches sort
        "Ultimrank": ["2", "5", "1"],
        "RaceVolatility": ["Low", "High", "Med"],
        "BuccaneerRank": ["1", "3", "2"],
        "BuccanneerPoints": ["100", "50", "80"],
        "ExtraColumn": ["ShouldBeDropped", "Ignored", "Bye"]
    }
    df = pd.DataFrame(data)
    file_path = tmp_path / "test_racing_data.csv"
    df.to_csv(file_path, index=False)
    return str(file_path)

def test_load_and_clean_data_columns(sample_csv):
    """Test that only the 19 required columns are kept."""
    df = process_racing_data.load_and_clean_data(sample_csv)
    
    expected_cols = [
        "Venue", "RN", "TN", "Horse Name", "Today Price", "Line of Betting", 
        "Race Group", "Race Class", "Today Dist", "Track Condition", "No. Starters", 
        "Today Race PM", "Comments", "OneHundredRatings", "Ultimrating", 
        "Ultimrank", "RaceVolatility", "BuccaneerRank", "BuccanneerPoints"
    ]
    
    assert list(df.columns) == expected_cols
    assert "ExtraColumn" not in df.columns

def test_sort_logic(sample_csv):
    """Test sorting: Venue (Asc) -> RN (Asc) -> Ultimrating (Desc)."""
    df = process_racing_data.load_and_clean_data(sample_csv)
    
    # Expected Order:
    # 1. Melbourne, RN 1, Ultimrating 70
    # 2. Sydney, RN 1, Ultimrating 100
    # 3. Sydney, RN 2, Ultimrating 90
    
    assert df.iloc[0]["Venue"] == "Melbourne"
    assert df.iloc[1]["Venue"] == "Sydney"
    assert df.iloc[1]["RN"] == 1
    assert df.iloc[2]["Venue"] == "Sydney"
    assert df.iloc[2]["RN"] == 2

def test_numeric_coercion(tmp_path):
    """Test that RN and Ultimrating are converted to numbers."""
    data = {
        "Venue": ["A", "A"],
        "RN": ["1", "NotANumber"],
        "TN": ["1", "1"],
        "Horse Name": ["H1", "H2"],
        "Today Price": ["1", "1"],
        "Line of Betting": ["1", "1"],
        "Race Group": ["G1", "G1"],
        "Race Class": ["C1", "C1"],
        "Today Dist": ["1000", "1000"],
        "Track Condition": ["G", "G"],
        "No. Starters": ["10", "10"],
        "Today Race PM": ["12:00", "12:00"],
        "Comments": ["C1", "C2"],
        "OneHundredRatings": ["100", "100"],
        "Ultimrating": ["90", "80"],
        "Ultimrank": ["1", "2"],
        "RaceVolatility": ["L", "L"],
        "BuccaneerRank": ["1", "1"],
        "BuccanneerPoints": ["10", "10"]
    }
    df = pd.DataFrame(data)
    file_path = tmp_path / "test_numeric.csv"
    df.to_csv(file_path, index=False)
    
    cleaned = process_racing_data.load_and_clean_data(str(file_path))
    
    # "NotANumber" should become NaN
    assert pd.isna(cleaned.iloc[1]["RN"])

def test_missing_column(tmp_path):
    """Test that a missing critical column raises KeyError."""
    data = {"Venue": ["Sydney"], "RN": ["1"]} # Missing almost everything
    df = pd.DataFrame(data)
    file_path = tmp_path / "bad_data.csv"
    df.to_csv(file_path, index=False)
    
    with pytest.raises(KeyError):
        process_racing_data.load_and_clean_data(str(file_path))
