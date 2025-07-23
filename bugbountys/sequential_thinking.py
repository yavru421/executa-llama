def tool_sequential_thinking(argstr):
    """
    Tool wrapper for sequential_thinking. Accepts a JSON string (single object or list) and returns the result as JSON.
    """
    try:
        data = json.loads(argstr)
        if isinstance(data, dict):
            data = [data]
        return json.dumps(sequential_thinking(data), indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Error: {e}"
#!/usr/bin/env python3

import argparse
import json

def sequential_thinking(thought_steps):
    """
    Processes a sequence of thought steps, each as a dict with keys:
    - thought, nextThoughtNeeded, thoughtNumber, totalThoughts, branchFromThought, branchId, isRevision, revisesThought, needsMoreThoughts
    Returns a list of processed steps with solution hypotheses and verification.
    """
    results = []
    for step in thought_steps:
        result = {
            "thought": step.get("thought"),
            "thoughtNumber": step.get("thoughtNumber"),
            "totalThoughts": step.get("totalThoughts"),
            "nextThoughtNeeded": step.get("nextThoughtNeeded", False),
        }
        if step.get("branchFromThought") is not None:
            result["branchFromThought"] = step["branchFromThought"]
        if step.get("branchId") is not None:
            result["branchId"] = step["branchId"]
        if step.get("isRevision"):
            result["isRevision"] = True
            if step.get("revisesThought") is not None:
                result["revisesThought"] = step["revisesThought"]
        if step.get("needsMoreThoughts"):
            result["needsMoreThoughts"] = True

        # Solution hypothesis and verification
        if not step.get("nextThoughtNeeded", False):
            result["solutionHypothesis"] = f"Final thought reached at step {step.get('thoughtNumber')}: {step.get('thought')}"
            result["verified"] = True
        else:
            result["solutionHypothesis"] = f"Continue thinking after step {step.get('thoughtNumber')}"
            result["verified"] = False
        results.append(result)
    return results


def main():
    parser = argparse.ArgumentParser(description="Sequential Thinking CLI Tool")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--json-file", type=str, help="Path to a JSON file containing a list of thought steps.")
    group.add_argument("--thought", type=str, action="append", help="Current thinking step (can be used multiple times for a sequence)")
    parser.add_argument("--next-thought-needed", action="append", choices=["true","false"], help="Whether another thought step is needed (true/false, matches --thought order)")
    parser.add_argument("--thought-number", type=int, action="append", help="Current thought number (matches --thought order)")
    parser.add_argument("--total-thoughts", type=int, action="append", help="Estimated total thoughts needed (matches --thought order)")
    parser.add_argument("--branch-from-thought", type=int, action="append", help="Branching point thought number (optional, matches --thought order)")
    parser.add_argument("--branch-id", type=str, action="append", help="Branch identifier (optional, matches --thought order)")
    parser.add_argument("--is-revision", action="append", choices=["true","false"], help="Whether this revises previous thinking (true/false, matches --thought order)")
    parser.add_argument("--revises-thought", type=int, action="append", help="Which thought is being reconsidered (optional, matches --thought order)")
    parser.add_argument("--needs-more-thoughts", action="append", choices=["true","false"], help="If more thoughts are needed (true/false, matches --thought order)")

    args = parser.parse_args()

    if args.json_file:
        with open(args.json_file, 'r', encoding='utf-8') as f:
            thought_steps = json.load(f)
    else:
        # Build list of steps from repeated CLI args
        n = len(args.thought)
        def get_arg_list(arg, default=None):
            return (arg if arg is not None else [default]*n) if isinstance(arg, list) else [default]*n

        thought_steps = []
        for i in range(n):
            step = {
                "thought": args.thought[i],
                "thoughtNumber": get_arg_list(args.thought_number)[i],
                "totalThoughts": get_arg_list(args.total_thoughts)[i],
                "nextThoughtNeeded": get_arg_list(args.next_thought_needed, "false")[i] == "true",
            }
            if args.branch_from_thought:
                step["branchFromThought"] = get_arg_list(args.branch_from_thought)[i]
            if args.branch_id:
                step["branchId"] = get_arg_list(args.branch_id)[i]
            if args.is_revision:
                step["isRevision"] = get_arg_list(args.is_revision, "false")[i] == "true"
            if args.revises_thought:
                step["revisesThought"] = get_arg_list(args.revises_thought)[i]
            if args.needs_more_thoughts:
                step["needsMoreThoughts"] = get_arg_list(args.needs_more_thoughts, "false")[i] == "true"
            thought_steps.append(step)

    results = sequential_thinking(thought_steps)
    print(json.dumps(results, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
