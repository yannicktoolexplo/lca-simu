import data_processor  
import model_trainer  
import model_evaluator  
  
def run_pipeline():  
    # Load and clean data  
    raw_data = data_processor.load_data()  
    cleaned_data = data_processor.clean_data(raw_data)  
    processed_data = data_processor.process_data(cleaned_data)  
  
    # Train model  
    model = model_trainer.train_model(processed_data)  
    model_trainer.save_model(model)  
  
    # Evaluate model  
    evaluation_results = model_evaluator.evaluate_model(model)  
    print(evaluation_results)  
  
if __name__ == "__main__":  
    run_pipeline()