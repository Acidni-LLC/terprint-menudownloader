---
description: 'Patterns for sharing business logic across Terprint applications - Python packages, NuGet packages, and API-first approaches'
applyTo: '**/core/**,**/shared/**,**/domain/**,**/business/**,**/*service*.py,**/*service*.cs,**/*Service*.cs'
---

# Shared Business Logic Instructions

## [!] CRITICAL: BUSINESS LOGIC MUST BE CENTRALIZED [!]

> **DO NOT duplicate business logic across repositories**

- Business logic belongs in **shared packages** (terprint-core)
- Application code **consumes** business logic, doesn't **implement** it
- Changes to business rules should happen in ONE place

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    terprint-core Repository                  │
│                                                             │
│  ┌─────────────────────┐    ┌─────────────────────────────┐ │
│  │ src/python/         │    │ src/dotnet/                 │ │
│  │ terprint_core/      │    │ Terprint.Core/              │ │
│  │                     │    │                             │ │
│  │ Published to:       │    │ Published to:               │ │
│  │ Azure Artifacts     │    │ Azure Artifacts             │ │
│  │ (PyPI feed)         │    │ (NuGet feed)                │ │
│  └─────────────────────┘    └─────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Business Logic Domains

| Domain | Description | Key Functions |
|--------|-------------|---------------|
| **Recommendations** | Strain similarity, product suggestions | `find_similar_strains()`, `get_recommendations()` |
| **Terpene Analysis** | Terpene profile calculations, effects | `calculate_profile_similarity()`, `predict_effects()` |
| **Pricing** | Price calculations, discounts, deals | `calculate_deal_value()`, `apply_discount_rules()` |
| **Stock** | Availability logic, inventory rules | `check_availability()`, `get_nearby_stock()` |
| **COA Parsing** | Certificate of Analysis extraction | `parse_coa()`, `extract_cannabinoids()` |
| **Metering** | Usage tracking, billing calculations | `calculate_usage()`, `apply_tier_limits()` |

## Python Package: terprint-core

### Installation

```bash
# Install from Azure Artifacts
pip install terprint-core --index-url https://pkgs.dev.azure.com/Acidni/Terprint/_packaging/terprint/pypi/simple/
```

### Package Structure

```
terprint-core/
├── src/
│   └── terprint_core/
│       ├── __init__.py
│       ├── recommendations/
│       │   ├── __init__.py
│       │   ├── similarity.py      # Strain similarity algorithms
│       │   ├── effects.py         # Effect-based matching
│       │   └── models.py          # Data models
│       ├── terpenes/
│       │   ├── __init__.py
│       │   ├── profiles.py        # Profile calculations
│       │   ├── effects.py         # Terpene effect mappings
│       │   └── constants.py       # Known terpenes, thresholds
│       ├── pricing/
│       │   ├── __init__.py
│       │   ├── deals.py           # Deal calculations
│       │   └── discounts.py       # Discount rules
│       └── coa/
│           ├── __init__.py
│           ├── parser.py          # COA parsing logic
│           └── extractors.py      # Field extraction
├── tests/
├── pyproject.toml
└── README.md
```

### Example: Strain Similarity (Python)

```python
# terprint_core/recommendations/similarity.py
from dataclasses import dataclass
from typing import List
import numpy as np

@dataclass
class TerpeneProfile:
    """Terpene profile for a strain."""
    strain_id: str
    strain_name: str
    myrcene: float = 0.0
    limonene: float = 0.0
    caryophyllene: float = 0.0
    pinene: float = 0.0
    linalool: float = 0.0
    humulene: float = 0.0
    terpinolene: float = 0.0
    ocimene: float = 0.0
    
    def to_vector(self) -> np.ndarray:
        """Convert profile to numpy vector for similarity calculations."""
        return np.array([
            self.myrcene, self.limonene, self.caryophyllene,
            self.pinene, self.linalool, self.humulene,
            self.terpinolene, self.ocimene
        ])

@dataclass
class SimilarityResult:
    """Result of strain similarity calculation."""
    strain_id: str
    strain_name: str
    similarity_score: float  # 0.0 to 1.0
    matching_terpenes: List[str]

def calculate_cosine_similarity(profile1: TerpeneProfile, profile2: TerpeneProfile) -> float:
    """
    Calculate cosine similarity between two terpene profiles.
    
    Returns:
        Similarity score from 0.0 (no similarity) to 1.0 (identical).
    """
    v1 = profile1.to_vector()
    v2 = profile2.to_vector()
    
    dot_product = np.dot(v1, v2)
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    return float(dot_product / (norm1 * norm2))

def find_similar_strains(
    target: TerpeneProfile,
    candidates: List[TerpeneProfile],
    min_similarity: float = 0.7,
    max_results: int = 10
) -> List[SimilarityResult]:
    """
    Find strains with similar terpene profiles.
    
    Args:
        target: The strain to find similarities for
        candidates: List of strains to compare against
        min_similarity: Minimum similarity score (0.0-1.0)
        max_results: Maximum number of results to return
        
    Returns:
        List of similar strains, sorted by similarity descending.
    """
    results = []
    
    for candidate in candidates:
        if candidate.strain_id == target.strain_id:
            continue
            
        similarity = calculate_cosine_similarity(target, candidate)
        
        if similarity >= min_similarity:
            # Find which terpenes are matching (both > threshold)
            matching = []
            threshold = 0.5  # Both must have > 0.5% to be "matching"
            
            for terpene in ['myrcene', 'limonene', 'caryophyllene', 'pinene', 
                           'linalool', 'humulene', 'terpinolene', 'ocimene']:
                if (getattr(target, terpene) > threshold and 
                    getattr(candidate, terpene) > threshold):
                    matching.append(terpene)
            
            results.append(SimilarityResult(
                strain_id=candidate.strain_id,
                strain_name=candidate.strain_name,
                similarity_score=similarity,
                matching_terpenes=matching
            ))
    
    # Sort by similarity descending
    results.sort(key=lambda x: x.similarity_score, reverse=True)
    
    return results[:max_results]
```

### Using in Python Function Apps

```python
# In func-terprint-ai-recommender
from terprint_core.recommendations import find_similar_strains, TerpeneProfile

async def get_recommendations(strain_id: str) -> List[dict]:
    """Get strain recommendations using shared business logic."""
    
    # Fetch data from Data API (via APIM)
    target_strain = await data_client.get_strain(strain_id)
    all_strains = await data_client.get_all_strains()
    
    # Convert to domain models
    target = TerpeneProfile(**target_strain)
    candidates = [TerpeneProfile(**s) for s in all_strains]
    
    # Use shared business logic
    similar = find_similar_strains(
        target=target,
        candidates=candidates,
        min_similarity=0.75,
        max_results=5
    )
    
    return [asdict(s) for s in similar]
```

## .NET Package: Terprint.Core

### Installation

```xml
<!-- In your .csproj -->
<ItemGroup>
  <PackageReference Include="Terprint.Core" Version="1.*" />
</ItemGroup>

<!-- nuget.config -->
<configuration>
  <packageSources>
    <add key="Terprint" value="https://pkgs.dev.azure.com/Acidni/Terprint/_packaging/terprint/nuget/v3/index.json" />
  </packageSources>
</configuration>
```

### Package Structure

```
Terprint.Core/
├── src/
│   └── Terprint.Core/
│       ├── Recommendations/
│       │   ├── StrainSimilarity.cs
│       │   ├── EffectMatcher.cs
│       │   └── Models/
│       │       ├── TerpeneProfile.cs
│       │       └── SimilarityResult.cs
│       ├── Terpenes/
│       │   ├── ProfileCalculator.cs
│       │   └── EffectPredictor.cs
│       ├── Pricing/
│       │   ├── DealCalculator.cs
│       │   └── DiscountRules.cs
│       └── Terprint.Core.csproj
├── tests/
│   └── Terprint.Core.Tests/
├── Terprint.Core.sln
└── README.md
```

### Example: Strain Similarity (C#)

```csharp
// Terprint.Core/Recommendations/StrainSimilarity.cs
namespace Terprint.Core.Recommendations;

public record TerpeneProfile(
    string StrainId,
    string StrainName,
    double Myrcene = 0,
    double Limonene = 0,
    double Caryophyllene = 0,
    double Pinene = 0,
    double Linalool = 0,
    double Humulene = 0,
    double Terpinolene = 0,
    double Ocimene = 0
)
{
    public double[] ToVector() => new[]
    {
        Myrcene, Limonene, Caryophyllene, Pinene,
        Linalool, Humulene, Terpinolene, Ocimene
    };
}

public record SimilarityResult(
    string StrainId,
    string StrainName,
    double SimilarityScore,
    IReadOnlyList<string> MatchingTerpenes
);

public static class StrainSimilarity
{
    /// <summary>
    /// Calculate cosine similarity between two terpene profiles.
    /// </summary>
    public static double CalculateCosineSimilarity(TerpeneProfile profile1, TerpeneProfile profile2)
    {
        var v1 = profile1.ToVector();
        var v2 = profile2.ToVector();
        
        var dotProduct = v1.Zip(v2, (a, b) => a * b).Sum();
        var norm1 = Math.Sqrt(v1.Sum(x => x * x));
        var norm2 = Math.Sqrt(v2.Sum(x => x * x));
        
        if (norm1 == 0 || norm2 == 0)
            return 0;
            
        return dotProduct / (norm1 * norm2);
    }
    
    /// <summary>
    /// Find strains with similar terpene profiles.
    /// </summary>
    public static IReadOnlyList<SimilarityResult> FindSimilarStrains(
        TerpeneProfile target,
        IEnumerable<TerpeneProfile> candidates,
        double minSimilarity = 0.7,
        int maxResults = 10)
    {
        var results = new List<SimilarityResult>();
        const double threshold = 0.5;
        
        foreach (var candidate in candidates)
        {
            if (candidate.StrainId == target.StrainId)
                continue;
                
            var similarity = CalculateCosineSimilarity(target, candidate);
            
            if (similarity >= minSimilarity)
            {
                var matching = GetMatchingTerpenes(target, candidate, threshold);
                
                results.Add(new SimilarityResult(
                    candidate.StrainId,
                    candidate.StrainName,
                    similarity,
                    matching
                ));
            }
        }
        
        return results
            .OrderByDescending(r => r.SimilarityScore)
            .Take(maxResults)
            .ToList();
    }
    
    private static IReadOnlyList<string> GetMatchingTerpenes(
        TerpeneProfile target, 
        TerpeneProfile candidate, 
        double threshold)
    {
        var matching = new List<string>();
        
        if (target.Myrcene > threshold && candidate.Myrcene > threshold)
            matching.Add("myrcene");
        if (target.Limonene > threshold && candidate.Limonene > threshold)
            matching.Add("limonene");
        // ... etc for other terpenes
            
        return matching;
    }
}
```

### Using in Terprint.Web

```csharp
// In Terprint.Web/Services/RecommendationService.cs
using Terprint.Core.Recommendations;

public class RecommendationService : IRecommendationService
{
    private readonly IStrainRepository _strainRepository;
    
    public async Task<IReadOnlyList<SimilarityResult>> GetRecommendationsAsync(string strainId)
    {
        // Fetch data
        var targetStrain = await _strainRepository.GetByIdAsync(strainId);
        var allStrains = await _strainRepository.GetAllAsync();
        
        // Convert to domain models
        var target = MapToProfile(targetStrain);
        var candidates = allStrains.Select(MapToProfile).ToList();
        
        // Use shared business logic from Terprint.Core
        return StrainSimilarity.FindSimilarStrains(
            target: target,
            candidates: candidates,
            minSimilarity: 0.75,
            maxResults: 5
        );
    }
    
    private static TerpeneProfile MapToProfile(Strain strain) => new(
        StrainId: strain.Id,
        StrainName: strain.Name,
        Myrcene: strain.TerpeneProfile?.Myrcene ?? 0,
        Limonene: strain.TerpeneProfile?.Limonene ?? 0
        // ... etc
    );
}
```

## Keeping Python & .NET in Sync

### Strategy 1: Shared Specification

Create a shared specification document that both implementations follow:

```yaml
# terprint-core/specs/strain-similarity.yaml
name: Strain Similarity Algorithm
version: 1.0.0

inputs:
  - name: target
    type: TerpeneProfile
  - name: candidates
    type: List[TerpeneProfile]
  - name: min_similarity
    type: float
    default: 0.7
  - name: max_results
    type: int
    default: 10

algorithm:
  - Calculate cosine similarity between target and each candidate
  - Filter by min_similarity threshold
  - Sort by similarity descending
  - Return top max_results

output:
  type: List[SimilarityResult]
  
test_cases:
  - name: "Identical profiles return 1.0"
    target: { myrcene: 1.0, limonene: 0.5 }
    candidate: { myrcene: 1.0, limonene: 0.5 }
    expected_similarity: 1.0
```

### Strategy 2: Shared Test Cases

```json
// terprint-core/tests/shared/similarity-test-cases.json
{
  "test_cases": [
    {
      "name": "High myrcene similarity",
      "target": { "myrcene": 2.5, "limonene": 0.3 },
      "candidate": { "myrcene": 2.8, "limonene": 0.2 },
      "expected_similarity_min": 0.95
    },
    {
      "name": "Different dominant terpenes",
      "target": { "myrcene": 2.5, "limonene": 0.1 },
      "candidate": { "myrcene": 0.1, "limonene": 2.5 },
      "expected_similarity_max": 0.3
    }
  ]
}
```

Both Python and .NET test suites load these shared test cases.

## API-First Alternative

For cross-language scenarios where packages are impractical, use the **API-first** approach:

```
┌─────────────────────────────────────────────────┐
│  func-terprint-ai-recommender (OWNS the logic)  │
│  - Implements recommendation algorithms         │
│  - Single source of truth                       │
│  - Exposed via APIM at /recommend               │
└─────────────────────────────────────────────────┘
                    │
                    ▼ (via APIM)
    ┌───────────────┴───────────────┐
    ▼                               ▼
┌─────────────┐             ┌─────────────┐
│ Terprint.Web│             │ AI Chat     │
│ (C#)        │             │ (Python)    │
│             │             │             │
│ Calls:      │             │ Calls:      │
│ /recommend/ │             │ /recommend/ │
└─────────────┘             └─────────────┘
```

```python
# Any app can call the recommender service
from terprint_config.apim import TerprintAPIClient

client = TerprintAPIClient()
recommendations = await client.get_recommendations(strain_id="abc123")
```

## When to Use Each Approach

| Scenario | Approach | Reason |
|----------|----------|--------|
| Same algorithm, multiple Python apps | `terprint-core` Python package | Direct, fast, type-safe |
| Same algorithm, multiple .NET apps | `Terprint.Core` NuGet package | Direct, fast, type-safe |
| Cross-language (Python + .NET) | API-first OR both packages | Depends on latency requirements |
| Rapid iteration on algorithm | API-first | Deploy once, all consumers updated |
| Offline/low-latency requirements | Packages | No network dependency |
| Complex stateful logic | API-first | Centralized state management |

## Publishing Packages

### Python to Azure Artifacts

```bash
# Build
cd terprint-core/src/python
python -m build

# Publish
twine upload --repository-url https://pkgs.dev.azure.com/Acidni/Terprint/_packaging/terprint/pypi/upload/ dist/*
```

### .NET to Azure Artifacts

```bash
# Build
cd terprint-core/src/dotnet
dotnet pack -c Release

# Publish
dotnet nuget push bin/Release/*.nupkg --source https://pkgs.dev.azure.com/Acidni/Terprint/_packaging/terprint/nuget/v3/index.json --api-key az
```

## Migration Path

### Phase 1: Extract to Local Module
Move business logic to a `core/` or `domain/` folder within existing repo.

### Phase 2: Create Shared Package
Extract to `terprint-core` repo, publish to Azure Artifacts.

### Phase 3: Update Consumers
Replace local implementations with package imports.

### Phase 4: Deprecate Duplicates
Remove duplicate logic from consumer repos.

## Adding New Business Logic

1. **Identify the domain** - Recommendations, Terpenes, Pricing, etc.
2. **Write the specification** - Document inputs, outputs, algorithm
3. **Implement in Python** - `terprint_core/{domain}/`
4. **Implement in .NET** - `Terprint.Core/{Domain}/`
5. **Write shared test cases** - JSON test case files
6. **Publish packages** - To Azure Artifacts
7. **Update consumers** - Import from packages

## Code Review Checklist

- [ ] Business logic is in `terprint-core`, not in consumer apps
- [ ] Python and .NET implementations follow the same specification
- [ ] Shared test cases pass in both languages
- [ ] No duplicate implementations across repos
- [ ] Package versions are pinned appropriately
