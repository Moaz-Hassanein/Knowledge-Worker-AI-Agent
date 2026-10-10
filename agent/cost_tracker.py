import memory_profiler
from langfuse import get_client
from dotenv import load_dotenv
from helpers.settings import get_settings

load_dotenv()


settings = get_settings()

MODEL_PRICES = {
"gpt-5.6-luna": {
"input_per_million": 0.20,
"output_per_million": 1.20,
},
"gpt-5.6-terra": {
"input_per_million": 2.00,
"output_per_million": 12.00,
},
"gpt-5.6-sol": {
"input_per_million": 4.00,
"output_per_million": 20.00,
},
}

class CostTracker:

    def __init__(self):

    # All LLM calls and normal pipeline steps
        self.calls = []
        self.model_name = None

    # Langfuse client
        self.langfuse = get_client()

    # RAM at the beginning of tracking
        self.start_ram = self.get_ram_usage()

# ========================================================
# RAM PROFILING
# ========================================================

    def get_ram_usage(self):
        """
        Return current RAM usage of the Python process in MiB.
    """
        return memory_profiler.memory_usage()[0]

    def get_peak_ram(self):
        """
        Return current RAM usage.

        The actual pipeline peak is calculated
        in the final summary from recorded values.
        """
        return self.get_ram_usage()

# ========================================================
# COST CALCULATION
# ========================================================

    def calculate_model_cost(
        self,
        input_tokens,
        output_tokens,
        model_name=None,
    ):
        """
        Calculate the estimated API cost for a model.

        This is a comparison estimate based on
        the token usage recorded from the local model.
        """
        model_name = model_name or self.model_name
        if not isinstance(model_name, str):
            return 0.0
        prices = MODEL_PRICES.get(model_name)

        if prices is None:
            return 0.0

        input_cost = (
            input_tokens
            / 1_000_000
            * prices["input_per_million"]
        )

        output_cost = (
            output_tokens
            / 1_000_000
            * prices["output_per_million"]
        )

        return input_cost + output_cost

    def calculate_all_comparison_costs(
        self,
        input_tokens,
        output_tokens,
        model_name=None,
    ):
        """
        Calculate estimated API costs
        for all comparison models.
        """

        comparison_costs = {}

        for model_name in MODEL_PRICES:

            comparison_costs[model_name] = (
                self.calculate_model_cost(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    model_name=model_name,
                )
            )

        return comparison_costs

# ========================================================
# TRACK LLM CALL
# ========================================================

    def record(
        self,
        node_name,
        response,
        elapsed_time=None,
        model_name=None,
    ):
        """
        Record one LLM call.

        Each call stores:
        - input tokens
        - output tokens
        - total tokens
        - model
        - cost
        - execution time
        - RAM usage
        """
        model_name = model_name or self.model_name
        # RAM before processing/storing the result
        ram_before = self.get_ram_usage()

        # ----------------------------------------------------
        # TOKEN USAGE
        # ----------------------------------------------------

        usage = getattr(
            response,
            "usage_metadata",
            {},
        ) or {}

        input_tokens = usage.get(
            "input_tokens",
            0,
        )

        output_tokens = usage.get(
            "output_tokens",
            0,
        )

        total_tokens = usage.get(
            "total_tokens",
            input_tokens + output_tokens,
        )

        # ----------------------------------------------------
        # OLLAMA FALLBACK
        # ----------------------------------------------------

        if input_tokens == 0 and output_tokens == 0:

            metadata = getattr(
                response,
                "response_metadata",
                {},
            ) or {}

            input_tokens = metadata.get(
                "prompt_eval_count",
                0,
            )

            output_tokens = metadata.get(
                "eval_count",
                0,
            )

            total_tokens = (
                input_tokens
                + output_tokens
            )

        # ----------------------------------------------------
        # API COST COMPARISON
        # ----------------------------------------------------

        comparison_costs = (
            self.calculate_all_comparison_costs(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model_name=model_name,
            )
        )

        # ----------------------------------------------------
        # RAM AFTER PROCESSING
        # ----------------------------------------------------

        ram_after = self.get_ram_usage()

        ram_change = (
            ram_after
            - ram_before
        )

        # ----------------------------------------------------
        # STORE RECORD
        # ----------------------------------------------------

        call_record = {
            "call_number": len(self.calls) + 1,
            "node": node_name,
            "model_name": model_name,

            # Token usage
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,

            # Performance
            "time": elapsed_time or 0.0,

            # RAM
            "ram_before": ram_before,
            "ram_usage": ram_after,
            "ram_change": ram_change,

            # Local Ollama cost
            "actual_cost": 0.0,

            # Estimated API comparison
            "comparison_costs": comparison_costs,
        }

        self.calls.append(
            call_record
        )

        # ----------------------------------------------------
        # PRINT LLM CALL
        # ----------------------------------------------------

        print("\n" + "-" * 60)
        print(
            f"[LLM CALL #{call_record['call_number']}] "
            f"{node_name}"
        )
        print("-" * 60)

        print(f"Model:          {model_name}")
        print(f"Input tokens:   {input_tokens}")
        print(f"Output tokens:  {output_tokens}")
        print(f"Total tokens:   {total_tokens}")
        
        if elapsed_time is not None:
            print(
                f"Time:           "
                f"{elapsed_time:.3f}s"
            )

        print(
            f"RAM before:     "
            f"{ram_before:.2f} MiB"
        )

        print(
            f"RAM after:      "
            f"{ram_after:.2f} MiB"
        )

        print(
            f"RAM change:     "
            f"{ram_change:+.2f} MiB"
        )

        print("-" * 60)

        # ----------------------------------------------------
        # COST COMPARISON FOR THIS CALL
        # ----------------------------------------------------

        print(
            "\nEstimated OpenAI API cost:"
        )

        for model_name, cost in (
            comparison_costs.items()
        ):

            print(
                f"  {model_name}: "
                f"${cost:.8f}"
            )

        print(
            "\nActual Ollama API cost: "
            "$0.00000000"
        )

        print(
            "-" * 60
        )

# ========================================================
# TRACK NORMAL PYTHON STEP
# ========================================================

    def record_step(
        self,
        step_name,
        elapsed_time,
        ram_before=None,
    ):


        if ram_before is None:
            ram_before = self.get_ram_usage()

        ram_after = self.get_ram_usage()

        ram_change = (
            ram_after
            - ram_before
        )

        self.calls.append({
            "call_number": len(self.calls) + 1,

            "node": step_name,

            "model": None,

            # No LLM tokens
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,

            # Performance
            "time": elapsed_time,

            # RAM
            "ram_before": ram_before,
            "ram_usage": ram_after,
            "ram_change": ram_change,

            # Cost
            "actual_cost": 0.0,

            # No API comparison for normal Python step
            "comparison_costs": {},
        })

        print(
            f"[STEP] {step_name}: "
            f"{elapsed_time:.3f}s"
        )

        print(
            f"       RAM before: "
            f"{ram_before:.2f} MiB"
        )

        print(
            f"       RAM after: "
            f"{ram_after:.2f} MiB"
        )

        print(
            f"       Change: "
            f"{ram_change:+.2f} MiB"
        )

# ========================================================
# GET SUMMARY
# ========================================================

    def get_summary(self):
        # Calculate a total of all recorded calls and steps.

        total_input = sum(
            call["input_tokens"]
            for call in self.calls
        )

        total_output = sum(
            call["output_tokens"]
            for call in self.calls
        )

        total_tokens = sum(
            call["total_tokens"]
            for call in self.calls
        )

        total_time = sum(
            call["time"]
            for call in self.calls
        )

        comparison_totals = {
            model_name: 0.0
            for model_name in MODEL_PRICES
        }

        llm_calls = [
            call
            for call in self.calls
            if call["total_tokens"] > 0
        ]

        for call in self.calls:

            comparison_costs = (
                call.get(
                    "comparison_costs",
                    {},
                )
            )

            for model_name in MODEL_PRICES:

                comparison_totals[
                    model_name
                ] += comparison_costs.get(
                    model_name,
                    0.0,
                )

        final_ram = self.get_ram_usage()

        ram_values = [
            self.start_ram,
            final_ram,
        ]

        ram_values.extend(
            call["ram_usage"]
            for call in self.calls
        )

        peak_ram = max(
            ram_values
        )

        return {
            # Calls
            "total_llm_calls": len(llm_calls),
            "total_pipeline_calls": len(self.calls),

            # Tokens
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_tokens": total_tokens,

            # Performance
            "total_execution_time": total_time,

            "model": self.model_name,

            # Local cost
            "actual_ollama_api_cost": 0.0,

            # API comparison
            "estimated_openai_api_costs":
                comparison_totals,

            # RAM
            "initial_ram_mib":
                self.start_ram,

            "final_ram_mib":
                final_ram,

            "peak_ram_mib":
                peak_ram,

            "ram_change_mib":
                final_ram
                - self.start_ram,

            "call_details": self.calls,
        }


# ========================================================
# FINAL SUMMARY
# ========================================================

    def print_summary(self):

        summary = self.get_summary()

        print(
            "\n"
            + "=" * 60
        )

        print(
            "LLM / PIPELINE USAGE SUMMARY"
        )

        print(
            "=" * 60
        )

        # ----------------------------------------------------
        # CALL DETAILS
        # ----------------------------------------------------

        for call in self.calls:

            print(
                f"{call['node']}: "
                f"input={call['input_tokens']}, "
                f"output={call['output_tokens']}, "
                f"total={call['total_tokens']}, "
                f"time={call['time']:.3f}s, "
                f"RAM={call['ram_usage']:.2f} MiB"
            )

       
        
        # ----------------------------------------------------
        # COST COMPARISON
        # ----------------------------------------------------

        print(
            "\n"
            + "-" * 60
        )

        print(
            "ESTIMATED API COST COMPARISON"
        )

        print(
            "-" * 60
        )

        print(
            "These are estimates based on the "
            "tokens used by the local Ollama model."
        )

        for (
            model_name,
            total_cost,
        ) in (
            summary[
                "estimated_openai_api_costs"
            ].items()
        ):

            print(
                f"{model_name}: "
                f"${total_cost:.8f}"
            )



        # ----------------------------------------------------
        # RAM SUMMARY
        # ----------------------------------------------------
        """
        print(
            "\n"
            + "-" * 60
        )

        print(
            "MEMORY SUMMARY"
        )

        print(
            "-" * 60
        )

        print(
            f"Initial RAM usage:   "
            f"{summary['initial_ram_mib']:.2f} MiB"
        )

        print(
            f"Final RAM usage:     "
            f"{summary['final_ram_mib']:.2f} MiB"
        )

        print(
            f"Peak RAM usage:      "
            f"{summary['peak_ram_mib']:.2f} MiB"
        )

        print(
            f"RAM increase:        "
            f"{summary['ram_change_mib']:+.2f} MiB"
        )

        # ----------------------------------------------------
        # MEMORY BY NODE
        # ----------------------------------------------------

        if self.calls:

            print(
                "\n"
                + "-" * 60
            )

            print(
                "MEMORY USAGE BY NODE"
            )

            print(
                "-" * 60
            )

            largest_increase = None

            for call in self.calls:

                ram_change = (
                    call["ram_change"]
                )

                print(
                    f"{call['node']}: "
                    f"{call['ram_usage']:.2f} MiB "
                    f"({ram_change:+.2f} MiB)"
                )

                if (
                    largest_increase is None
                    or ram_change
                    > largest_increase[1]
                ):

                    largest_increase = (
                        call["node"],
                        ram_change,
                    )

            # ------------------------------------------------
            # LARGEST MEMORY INCREASE
            # ------------------------------------------------

            if largest_increase:

                print(
                    "\n"
                    + "-" * 60
                )

                print(
                    f"Largest RAM increase: "
                    f"{largest_increase[0]} "
                    f"({largest_increase[1]:+.2f} MiB)"
                )"""

      
        # ----------------------------------------------------
        # TOTAL RESOURCES USED
        # ----------------------------------------------------

        print(
            "\n"
            + "=" * 60
        )

        print(
            "TOTAL RESOURCES USED"
        )

        print(
            "-" * 60
        )

        print(
            f"Total LLM calls:       "
            f"{summary['total_llm_calls']}"
        )

        print(
            f"Total input tokens:    "
            f"{summary['total_input_tokens']}"
        )

        print(
            f"Total output tokens:   "
            f"{summary['total_output_tokens']}"
        )

        print(
            f"Total tokens used:     "
            f"{summary['total_tokens']}"
        )

        print(
            f"Total execution time:  "
            f"{summary['total_execution_time']:.3f}s"
        )

        print(
            f"Total actual cost:     "
            f"${summary['actual_ollama_api_cost']:.8f}"
        )

        print(
            f"Peak RAM usage:        "
            f"{summary['peak_ram_mib']:.2f} MiB"
        )

        print(
            f"RAM increase:          "
            f"{summary['ram_change_mib']:+.2f} MiB"
        )

        print("=" * 60)


# ========================================================
# LANGFUSE FLUSH
# ========================================================

    def flush(self):
        """
        Send all pending Langfuse data.
        """

        self.langfuse.flush()


tracker = CostTracker()